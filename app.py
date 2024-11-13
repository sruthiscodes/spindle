"""from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS
import sqlite3
import bcrypt
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('bicycleRental.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

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
            Password VARCHAR(255) NOT NULL
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Bicycle (
            BicycleID VARCHAR(50) PRIMARY KEY,
            Status VARCHAR(20) NOT NULL,
            Location VARCHAR(100),
            Gear JSON
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
    bicycles = conn.execute('SELECT * FROM Bicycle WHERE Status = "Available"').fetchall()
    conn.close()
    return jsonify([dict(bicycle) for bicycle in bicycles])

# API to rent a bicycle
@app.route('/rent_bicycle', methods=['POST'])
def rent_bicycle():
    data = request.get_json()

    if not all(key in data for key in ['userID', 'bicycleID']):
        return jsonify({"error": "UserID and BicycleID are required!"}), 400

    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    try:
        bicycle = conn.execute('SELECT * FROM Bicycle WHERE BicycleID = ? AND Status = "Available"', (bicycleID,)).fetchone()

        if bicycle:
            conn.execute('UPDATE Bicycle SET Status = "Rented" WHERE BicycleID = ?', (bicycleID,))
            start_time = datetime.now()
            rentalID = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO Rents (RentalID, UserID, BicycleID, StartTime) VALUES (?, ?, ?, ?)',
                (rentalID, userID, bicycleID, start_time)
            )
            conn.commit()
            return jsonify({"message": "Bicycle rented successfully!"}), 201
        else:
            return jsonify({"error": "Bicycle is not available!"}), 400
    finally:
        conn.close()

# API to return a bicycle
@app.route('/return_bicycle', methods=['POST'])
def return_bicycle():
    data = request.get_json()

    if not all(key in data for key in ['userID', 'bicycleID']):
        return jsonify({"error": "UserID and BicycleID are required!"}), 400

    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    try:
        conn.execute('UPDATE Bicycle SET Status = "Available" WHERE BicycleID = ?', (bicycleID,))
        end_time = datetime.now()
        conn.execute(
            'UPDATE Rents SET EndTime = ? WHERE UserID = ? AND BicycleID = ?',
            (end_time, userID, bicycleID)
        )
        conn.commit()
        return jsonify({"message": "Bike returned successfully!"}), 200
    finally:
        conn.close()

# API to give a bicycle for rent
@app.route('/add_bike', methods=['POST'])
def add_bike():
    data = request.get_json()

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
    try:
        bicycleID = str(uuid.uuid4())
        conn.execute(
            'INSERT INTO Bicycle (BicycleID, Status, Location, Gear) VALUES (?, ?, ?, ?)',
            (bicycleID, 'Available', bikeLocation, '{"type": "' + bikeType + '", "pricePerHour": ' + str(bikePrice) + '}')
        )
        conn.commit()
        return jsonify({"message": "Bike added for rent successfully!"}), 201
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
"""

from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS
import sqlite3
import bcrypt
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('bicycleRental.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

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

    # Create trigger for renting a bicycle
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS after_rent_bicycle
        AFTER UPDATE ON Bicycle
        FOR EACH ROW
        WHEN NEW.Status = 'Rented'
        BEGIN
            INSERT INTO Rents (RentalID, BicycleID, UserID, StartTime) 
            VALUES (NEW.RentalID, NEW.BicycleID, NEW.UserID, datetime('now'));
        END;
    ''')

    # Create trigger for returning a bicycle
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS after_return_bicycle
        AFTER UPDATE ON Bicycle
        FOR EACH ROW
        WHEN NEW.Status = 'Available'
        BEGIN
            UPDATE Rents 
            SET EndTime = datetime('now') 
            WHERE BicycleID = NEW.BicycleID AND EndTime IS NULL;
        END;
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
    bicycles = conn.execute('SELECT * FROM Bicycle WHERE Status = "Available"').fetchall()
    conn.close()
    return jsonify([dict(bicycle) for bicycle in bicycles])

# API to rent a bicycle
@app.route('/rent_bicycle', methods=['POST'])
def rent_bicycle():
    data = request.get_json()

    if not all(key in data for key in ['userID', 'bicycleID']):
        return jsonify({"error": "UserID and BicycleID are required!"}), 400

    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    try:
        bicycle = conn.execute('SELECT * FROM Bicycle WHERE BicycleID = ? AND Status = "Available"', (bicycleID,)).fetchone()

        if bicycle:
            conn.execute('UPDATE Bicycle SET Status = "Rented" WHERE BicycleID = ?', (bicycleID,))
            start_time = datetime.now()
            rentalID = str(uuid.uuid4())
            conn.execute(
                'INSERT INTO Rents (RentalID, UserID, BicycleID, StartTime) VALUES (?, ?, ?, ?)',
                (rentalID, userID, bicycleID, start_time)
            )
            conn.commit()
            return jsonify({"message": "Bicycle rented successfully!"}), 201
        else:
            return jsonify({"error": "Bicycle is not available!"}), 400
    finally:
        conn.close()

# API to return a bicycle
@app.route('/return_bicycle', methods=['POST'])
def return_bicycle():
    data = request.get_json()

    if not all(key in data for key in ['userID', 'bicycleID']):
        return jsonify({"error": "UserID and BicycleID are required!"}), 400

    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    try:
        conn.execute('UPDATE Bicycle SET Status = "Available" WHERE BicycleID = ?', (bicycleID,))
        end_time = datetime.now()
        conn.execute(
            'UPDATE Rents SET EndTime = ? WHERE UserID = ? AND BicycleID = ?',
            (end_time, userID, bicycleID)
        )
        conn.commit()
        return jsonify({"message": "Bike returned successfully!"}), 200
    finally:
        conn.close()

# API to give a bicycle for rent
@app.route('/add_bike', methods=['POST'])
def add_bike():
    data = request.get_json()

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
    try:
        bicycleID = str(uuid.uuid4())
        conn.execute(
            'INSERT INTO Bicycle (BicycleID, Status, Location, Gear, UserID) VALUES (?, "Available", ?, ?, ?)',
            (bicycleID, bikeLocation, bikeType, userID)
        )
        conn.commit()
        return jsonify({"message": "Bike added for rent successfully!"}), 201
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)

