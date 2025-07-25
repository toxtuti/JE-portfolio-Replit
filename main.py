
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return '<h1>Hello, Flask!</h1><p>Your Flask app is running on Replit!</p>'

@app.route('/about')
def about():
    return '<h1>About</h1><p>This is a Flask application deployed on Replit.</p>'

@app.route('/api/data')
def get_data():
    return {
        "message": "Hello from Flask API!",
        "status": "success",
        "data": [1, 2, 3, 4, 5]
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
