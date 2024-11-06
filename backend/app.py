from flask import Flask, jsonify, request
import sqlite3
import hashlib
from datetime import datetime

app = Flask(__name__)

# Database connection
def get_db_connection():
    conn = sqlite3.connect('bicycleRental.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create all necessary tables
def create_tables():
    conn = get_db_connection()
    
    # Users Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Users (
        userID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT,
        emailID TEXT UNIQUE,
        phoneNo TEXT,
        password TEXT,
        DOB DATE
    );
    ''')
    
    # Bicycle Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Bicycle (
        bicycleID INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT,
        status TEXT
    );
    ''')
    
    # Gear Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Gear (
        gearID INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        status TEXT,
        bicycleID INTEGER,
        FOREIGN KEY (bicycleID) REFERENCES Bicycle(bicycleID)
    );
    ''')

    # Rents Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Rents (
        rentID INTEGER PRIMARY KEY AUTOINCREMENT,
        userID INTEGER,
        bicycleID INTEGER,
        startTime TIMESTAMP,
        endTime TIMESTAMP,
        FOREIGN KEY (userID) REFERENCES Users(userID),
        FOREIGN KEY (bicycleID) REFERENCES Bicycle(bicycleID)
    );
    ''')
    
    # Payment Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Payment (
        paymentID INTEGER PRIMARY KEY AUTOINCREMENT,
        userID INTEGER,
        amount DECIMAL,
        status TEXT,
        timestamp TIMESTAMP,
        FOREIGN KEY (userID) REFERENCES Users(userID)
    );
    ''')

    # Feedback Table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS Feedback (
        feedbackID INTEGER PRIMARY KEY AUTOINCREMENT,
        rentalID INTEGER,
        text TEXT,
        rating INTEGER,
        feedbackDate DATE,
        FOREIGN KEY (rentalID) REFERENCES Rents(rentID)
    );
    ''')

    conn.commit()
    conn.close()

# Route to get available bikes
@app.route('/bicycle', methods=['GET'])
def get_bikes():
    conn = get_db_connection()
    bicycles = conn.execute('SELECT * FROM Bicycle WHERE status = "Available"').fetchall()
    conn.close()
    return jsonify([dict(bicycle) for bicycle in bicycles])

# API for registering a new user
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data['name']
    emailID = data['emailID']
    phoneNo = data['phoneNo']
    password = hashlib.sha256(data['password'].encode()).hexdigest()  # Hash the password for security
    DOB = data['DOB']

    conn = get_db_connection()
    
    try:
        conn.execute('INSERT INTO Users (Name, emailID, phoneNo, password, DOB) VALUES (?, ?, ?, ?, ?)', 
                     (name, emailID, phoneNo, password, DOB))
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists!"}), 400
    finally:
        conn.close()

# API for user login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    emailID = data['emailID']
    password = hashlib.sha256(data['password'].encode()).hexdigest()  # Hash the password for comparison

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Users WHERE emailID = ? AND password = ?', (emailID, password)).fetchone()
    conn.close()

    if user:
        return jsonify({"message": "Login successful!", "userID": user['userID']})
    else:
        return jsonify({"error": "Invalid email or password!"}), 401

# API to rent a bicycle
@app.route('/rent_bicycle', methods=['POST'])
def rent_bicycle():
    data = request.get_json()
    userID = data['userID']
    bicycleID = data['bicycleID']

    conn = get_db_connection()
    # Check if the bicycle is available
    bicycle = conn.execute('SELECT * FROM Bicycle WHERE bicycleID = ? AND status = "Available"', (bicycleID,)).fetchone()
    
    if bicycle:
        # Mark bicycle as rented
        conn.execute('UPDATE Bicycle SET status = "Rented" WHERE bicycleID = ?', (bicycleID,))
        
        # Record the rental start time
        start_time = datetime.now()
        conn.execute('INSERT INTO Rents (userID, bicycleID, startTime) VALUES (?, ?, ?)', 
                     (userID, bicycleID, start_time))
        conn.commit()
        
        conn.close()
        return jsonify({"message": "Bicycle rented successfully!"}), 201
    else:
        conn.close()
        return jsonify({"error": "Bicycle is not available!"}), 400

# API to return a rented bicycle
@app.route('/return_bicycle', methods=['POST'])
def return_bicycle():
    data = request.get_json()
    rentID = data['rentID']
    
    conn = get_db_connection()
    
    # Fetch the rental details
    rental = conn.execute('SELECT * FROM Rents WHERE rentID = ?', (rentID,)).fetchone()
    
    if rental:
        # Mark bicycle as available
        conn.execute('UPDATE Bicycle SET status = "Available" WHERE bicycleID = ?', (rental['bicycleID'],))
        
        # Record the rental end time
        end_time = datetime.now()
        conn.execute('UPDATE Rents SET endTime = ? WHERE rentID = ?', (end_time, rentID))
        conn.commit()
        
        conn.close()
        return jsonify({"message": "Bicycle returned successfully!"}), 200
    else:
        conn.close()
        return jsonify({"error": "Rental record not found!"}), 400

if __name__ == "__main__":
    create_tables()  # Create tables at startup
    app.run(debug=True)
