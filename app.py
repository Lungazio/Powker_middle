# app.py - Main Flask application
from flask import Flask, render_template
from flask_socketio import SocketIO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Import and register lobby routes
from lobby import register_lobby_events
register_lobby_events(socketio)

# Import and register game routes  
from game import register_game_events
register_game_events(socketio)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game/<game_id>')
def game_room(game_id):
    return render_template('game_room.html', game_id=game_id)

@app.route('/health')
def health_check():
    from lobby import active_lobbies
    from game import active_games
    return {
        "status": "healthy", 
        "lobbies": len(active_lobbies),
        "games": len(active_games)
    }, 200

if __name__ == '__main__':
    logger.info("Starting Poker Flask App...")
    socketio.run(app, host='0.0.0.0', port=8001, debug=True)