from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS
import sqlite3
import bcrypt
from datetime import datetime
import uuid
import re
import json
import time

app = Flask(__name__)
CORS(app)

# Database connection function with timeout
def get_db_connection():
    conn = sqlite3.connect('bicycleRental.db', timeout=10.0)  # 10 seconds timeout for SQLite
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

# Retry mechanism for database operations
def execute_with_retry(conn, query, params=(), retries=3, delay=1):
    for attempt in range(retries):
        try:
            conn.execute(query, params)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < retries - 1:
                time.sleep(delay)
                continue
            else:
                raise

# Create tables if they don't exist
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID VARCHAR(50) PRIMARY KEY,
            Name VARCHAR(100) NOT NULL,
            EmailID VARCHAR(100) UNIQUE NOT NULL,
            PhoneNo VARCHAR(20),
            DOB DATE,
            Password VARCHAR(255) NOT NULL,
            CONSTRAINT valid_email CHECK(EmailID LIKE '%_@__%.__%')
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bicycle (
            BicycleID VARCHAR(50) PRIMARY KEY,
            Status VARCHAR(20) NOT NULL CHECK (Status IN ('Available', 'Rented')),
            Location VARCHAR(100),
            Gear JSON,
            UserID VARCHAR(50),
            FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Rents (
            RentalID VARCHAR(50) PRIMARY KEY,
            UserID VARCHAR(50),
            BicycleID VARCHAR(50),
            StartTime DATETIME NOT NULL,
            EndTime DATETIME,
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (BicycleID) REFERENCES Bicycle(BicycleID)
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Payments (
            PaymentID VARCHAR(50) PRIMARY KEY,
            UserID VARCHAR(50),
            RentalID VARCHAR(50),
            Amount DECIMAL(10, 2) NOT NULL,
            PaymentDate DATETIME NOT NULL,
            CardNumber VARCHAR(16),
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (RentalID) REFERENCES Rents(RentalID)
        );
    ''')

    conn.commit()
    conn.close()

# Run table creation on app start
create_tables()

# Serve the login page
@app.route('/')
@app.route('/login')
def login():
    return render_template('login.html')

# Serve the signup page
@app.route('/signup')
def signup():
    return render_template('signup.html')

# Serve the dashboard page (for viewing user rentals and available bikes)
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Serve the rent a bicycle page (where users can rent available bikes)
@app.route('/rent')
def rent_page():
    return render_template('rent.html')

# Serve the give rent page (where users can give their bike for rent)
@app.route('/give_rent')
def give_rent_page():
    return render_template('give_rent.html')

# Serve the payment page
@app.route('/payment')
def payment_page():
    return render_template('payment.html')

# API to register a new user
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # Validate required fields
    required_fields = ['name', 'emailID', 'phoneNo', 'password', 'DOB']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    name = data['name']
    emailID = data['emailID']
    phoneNo = data['phoneNo']
    password = data['password']
    DOB = data['DOB']

    # Password validation
    if not is_valid_password(password):
        return jsonify({"error": "Password does not meet the required criteria!"}), 400

    # Hash the password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = get_db_connection()

    try:
        conn.execute(
            'INSERT INTO Users (UserID, Name, EmailID, PhoneNo, Password, DOB) VALUES (?, ?, ?, ?, ?, ?)',
            (str(uuid.uuid4()), name, emailID, phoneNo, hashed_password, DOB)
        )
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists!"}), 400
    finally:
        conn.close()

def is_valid_password(password):
    if len(password) < 6:
        return False  # Minimum length is 6 characters
    if not re.search(r'[A-Z]', password):  # At least one uppercase letter
        return False
    if not re.search(r'[a-z]', password):  # At least one lowercase letter
        return False
    if not re.search(r'[0-9]', password):  # At least one digit
        return False
    if not re.search(r'[\W_]', password):  # At least one special character (non-alphanumeric)
        return False
    return True

# API for user login
@app.route('/login_user', methods=['POST'])
def login_user():
    data = request.get_json()

    if not all(key in data for key in ['emailID', 'password']):
        return jsonify({"error": "Email and password are required!"}), 400

    emailID = data['emailID']
    password = data['password']

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM Users WHERE EmailID = ?', (emailID,)).fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['Password']):
            return jsonify({"message": "Login successful!", "userID": user['UserID']}), 200
        else:
            return jsonify({"error": "Invalid email or password!"}), 401
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Login failed due to an internal error."}), 500
    finally:
        conn.close()

# API to get available bikes (for renting)
@app.route('/bicycles', methods=['GET'])
def get_bicycles():
    conn = get_db_connection()
    
    query = '''
    SELECT B.BicycleID, B.Status, B.Location, B.Gear, U.Name AS OwnerName
    FROM Bicycle B
    LEFT JOIN Users U ON B.UserID = U.UserID
    WHERE B.Status = "Available"
    '''
    bicycles = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(bicycle) for bicycle in bicycles])

# API to give a bicycle for rent (user uploads their own bike)
@app.route('/give_rent', methods=['POST'])
def give_rent():
    data = request.get_json()

    # Retrieve the data from the request body
    user_id = data.get('userID')
    location = data.get('location')
    gear = data.get('gear')

    # Validate required fields
    if not user_id or not location or not gear:
        return jsonify({"error": "Missing required data"}), 400

    # Check if the user exists in the Users table
    conn = get_db_connection()
    try:
        user_check = conn.execute('SELECT 1 FROM Users WHERE UserID = ?', (user_id,)).fetchone()
        if not user_check:
            return jsonify({"error": "UserID does not exist in the database!"}), 400
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Proceed with bike insertion only if the user exists
    bike_id = str(uuid.uuid4())

    try:
        with get_db_connection() as conn:
            # Execute the insert operation with retry mechanism
            execute_with_retry(conn,
                               'INSERT INTO Bicycle (BicycleID, Status, Location, Gear, UserID) VALUES (?, ?, ?, ?, ?)',
                               (bike_id, 'Available', location, json.dumps(gear), user_id))
        return jsonify({"message": "Bike added successfully!", "bikeID": bike_id}), 201
    except sqlite3.IntegrityError as e:
        return jsonify({"error": f"Failed to insert data due to integrity error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error occurred: {str(e)}"}), 500

# API to handle payment submission
@app.route('/make_payment', methods=['POST'])
def make_payment():
    data = request.get_json()

    # Validate required fields
    required_fields = ['userID', 'rentalID', 'cardNumber', 'amount']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    userID = data['userID']
    rentalID = data['rentalID']
    cardNumber = data['cardNumber'][-4:]  # Store only the last 4 digits of the card number
    amount = data['amount']

    conn = get_db_connection()
    try:
        paymentID = str(uuid.uuid4())
        conn.execute(
            '''
            INSERT INTO Payments (PaymentID, UserID, RentalID, Amount, PaymentDate, CardNumber) 
            VALUES (?, ?, ?, ?, ?, ?)
            ''', 
            (paymentID, userID, rentalID, amount, datetime.now(), cardNumber)
        )
        conn.commit()
        return jsonify({"message": "Payment successful!"}), 201
    finally:
        conn.close()

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
