from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS  # For Cross-Origin requests
import sqlite3
import bcrypt  # For password hashing
from datetime import datetime
import uuid  # For generating unique BicycleID

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('bicycleRental.db')
    conn.row_factory = sqlite3.Row  # To return rows as dictionaries
    conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign key constraints
    return conn

# Create tables if they do not exist
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID VARCHAR(50) PRIMARY KEY,
            Name VARCHAR(100) NOT NULL,
            EmailID VARCHAR(100) UNIQUE NOT NULL,
            PhoneNo VARCHAR(20),
            DOB DATE,
            Password VARCHAR(255) NOT NULL
        );
    ''')

    # Create Bicycle table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bicycle (
            BicycleID VARCHAR(50) PRIMARY KEY,
            Status VARCHAR(20) NOT NULL,
            Location VARCHAR(100),
            Gear JSON
        );
    ''')

    # Create Rents table
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

    # Create Payment table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Payment (
            PaymentID VARCHAR(50) PRIMARY KEY,
            UserID VARCHAR(50),
            Timestamp DATETIME NOT NULL,
            Status VARCHAR(20) NOT NULL,
            Amount DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (UserID) REFERENCES Users(UserID)
        );
    ''')

    # Create Feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Feedback (
            RentalID VARCHAR(50),
            FeedbackID VARCHAR(50),
            Text TEXT,
            Rating INT CHECK (Rating >= 1 AND Rating <= 5),
            FeedbackDate DATETIME NOT NULL,
            PRIMARY KEY (RentalID, FeedbackID),
            FOREIGN KEY (RentalID) REFERENCES Rents(RentalID)
                ON DELETE CASCADE
        );
    ''')

    # Create Ride_Feedback table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Ride_Feedback (
            FeedbackID VARCHAR(50) PRIMARY KEY,
            UserID VARCHAR(50),
            FOREIGN KEY (UserID) REFERENCES Users(UserID)
        );
    ''')

    # Create Paid table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Paid (
            PaymentID VARCHAR(50),
            UserID VARCHAR(50),
            RentalID VARCHAR(50),
            PRIMARY KEY (PaymentID, UserID, RentalID),
            FOREIGN KEY (PaymentID) REFERENCES Payment(PaymentID),
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (RentalID) REFERENCES Rents(RentalID)
        );
    ''')

    # Create indexes for better query performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_bicycle_status ON Bicycle(Status);
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_rents_dates ON Rents(StartTime, EndTime);
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_payment_status ON Payment(Status);
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_feedback_rental ON Feedback(RentalID);
    ''')

    conn.commit()
    conn.close()

# Run the function to create tables when the app starts
create_tables()

# Serve the homepage or login page
@app.route('/')
@app.route('/login')
def login():
    return render_template('login.html')

# Serve the signup page
@app.route('/signup')
def signup():
    return render_template('signup.html')

# Serve the page after successful login or rental page
@app.route('/page1')
def page1():
    return render_template('page1.html')

# API to register a new user
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data['name']
    emailID = data['emailID']
    phoneNo = data['phoneNo']
    password = data['password']
    DOB = data['DOB']

    # Hash the password with bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = get_db_connection()
    
    try:
        conn.execute('INSERT INTO Users (Name, EmailID, PhoneNo, Password, DOB) VALUES (?, ?, ?, ?, ?)', 
                     (name, emailID, phoneNo, hashed_password, DOB))
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists!"}), 400
    finally:
        conn.close()

# API for user login
'''@app.route('/login_user', methods=['POST'])
def login_user():
    data = request.get_json()
    emailID = data['emailID']
    password = data['password']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Users WHERE EmailID = ?', (emailID,)).fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['Password'].encode('utf-8')):
        return jsonify({"message": "Login successful!", "userID": user['UserID']})
    else:
        return jsonify({"error": "Invalid email or password!"}), 401'''
@app.route('/login_user', methods=['POST'])
def login_user():
    data = request.get_json()
    emailID = data['emailID']
    password = data['password']

    conn = get_db_connection()
    
    try:
        user = conn.execute('SELECT * FROM Users WHERE EmailID = ?', (emailID,)).fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user['Password'].encode('utf-8')):
            return jsonify({"message": "Login successful!", "userID": user['UserID']})
        else:
            return jsonify({"error": "Invalid email or password!"}), 401
    except Exception as e:
        # Log the error for debugging
        print(f"Error during login: {e}")
        return jsonify({"error": "An error occurred. Please try again later."}), 500
    finally:
        conn.close()


# API to get available bikes
@app.route('/bicycle', methods=['GET'])
def get_bikes():
    conn = get_db_connection()
    bicycles = conn.execute('SELECT * FROM Bicycle WHERE Status = "Available"').fetchall()
    conn.close()
    return jsonify([dict(bicycle) for bicycle in bicycles])

# API to rent a bicycle
@app.route('/rent_bicycle', methods=['POST'])
def rent_bicycle():
    data = request.get_json()
    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    # Check if the bicycle is available
    bicycle = conn.execute('SELECT * FROM Bicycle WHERE BicycleID = ? AND Status = "Available"', (bicycleID,)).fetchone()
    
    if bicycle:
        # Mark bicycle as rented
        conn.execute('UPDATE Bicycle SET Status = "Rented" WHERE BicycleID = ?', (bicycleID,))
        
        # Record the rental start time
        start_time = datetime.now()
        rentalID = str(uuid.uuid4())
        conn.execute('INSERT INTO Rents (RentalID, UserID, BicycleID, StartTime) VALUES (?, ?, ?, ?)', 
                     (rentalID, userID, bicycleID, start_time))
        conn.commit()
        
        conn.close()
        return jsonify({"message": "Bicycle rented successfully!"}), 201
    else:
        conn.close()
        return jsonify({"error": "Bicycle is not available!"}), 400

# API to return a bicycle
@app.route('/return_bicycle', methods=['POST'])
def return_bicycle():
    data = request.get_json()
    userID = data['userID']
    bicycleID = data['bicycleID']
    
    conn = get_db_connection()
    
    # Update bicycle status to "Available"
    conn.execute('UPDATE Bicycle SET Status = "Available" WHERE BicycleID = ?', (bicycleID,))
    
    # Update rental end time (instead of deleting)
    end_time = datetime.now()
    conn.execute('UPDATE Rents SET EndTime = ? WHERE UserID = ? AND BicycleID = ?', 
                 (end_time, userID, bicycleID))
    
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Bike returned successfully!"}), 200

# API to add a bicycle for rent (user can give their bike for rent)
@app.route('/add_bike', methods=['POST'])
def add_bike():
    data = request.get_json()

    # Validate input data
    required_fields = ['userID', 'bikeName', 'bikeType', 'bikeLocation', 'bikePrice']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    
    userID = data['userID']
    bikeName = data['bikeName']
    bikeType = data['bikeType']
    bikeLocation = data['bikeLocation']
    bikePrice = data['bikePrice']

    if not isinstance(bikePrice, (int, float)) or bikePrice <= 0:
        return jsonify({"error": "Invalid price value."}), 400

    conn = get_db_connection()

    # Generate a unique BicycleID
    bicycleID = str(uuid.uuid4())

    # Add bike entry into the Bicycle table
    conn.execute('INSERT INTO Bicycle (BicycleID, Status, Location, Gear) VALUES (?, ?, ?, ?)', 
                 (bicycleID, 'Available', bikeLocation, '{"type": "' + bikeType + '", "pricePerHour": ' + str(bikePrice) + '}'))
    conn.commit()
    conn.close()

    return jsonify({"message": "Bike added for rent successfully!"}), 201

if __name__ == "__main__":
    app.run(debug=True)
