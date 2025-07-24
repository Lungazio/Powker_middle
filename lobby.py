# lobby.py - Simple lobby management
from flask_socketio import emit, join_room, leave_room
from flask import request
import random
import logging
import secrets
from datetime import datetime

logger = logging.getLogger(__name__)

# Global state - resets on server restart
active_lobbies = {}
player_sessions = {}
used_codes = set()
player_tokens = {}  # Global token storage: token -> player_info
pending_game_players = {}  # gameId -> [list of players waiting to join]

def generate_lobby_code():
    """Generate unique 6-letter code"""
    letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ'  # No I, O
    while True:
        code = ''.join(random.choice(letters) for _ in range(6))
        if code not in used_codes and code not in active_lobbies:
            used_codes.add(code)
            return code

def register_lobby_events(socketio):
    """Register all lobby WebSocket events"""
    
    @socketio.on('connect')
    def handle_connect():
        socket_id = request.sid
        logger.info(f"Player connected: {socket_id}")
        player_sessions[socket_id] = {
            'username': None,
            'lobby_code': None
        }
        emit('connected', {'message': 'Connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        socket_id = request.sid
        logger.info(f"Player disconnected: {socket_id}")
        
        # Clean up player from lobby if they were in one
        if socket_id in player_sessions:
            lobby_code = player_sessions[socket_id].get('lobby_code')
            if lobby_code and lobby_code in active_lobbies:
                # Remove player from lobby
                lobby = active_lobbies[lobby_code]
                lobby['players'] = [p for p in lobby['players'] if p['socketId'] != socket_id]
                
                # Notify others
                socketio.emit('player_left', {'lobby': lobby}, room=f"lobby_{lobby_code}")
                
                # Clean up empty lobby
                if len(lobby['players']) == 0:
                    used_codes.discard(lobby_code)
                    del active_lobbies[lobby_code]
            
            del player_sessions[socket_id]
    
    @socketio.on('set_username')
    def handle_set_username(data):
        socket_id = request.sid
        username = data.get('username', '').strip()
        
        if not username or len(username) < 2:
            emit('username_error', {'error': 'Invalid username'})
            return
        
        player_sessions[socket_id]['username'] = username
        emit('username_set', {'username': username, 'message': 'Username set'})
    
    @socketio.on('create_lobby')
    def handle_create_lobby(data):
        socket_id = request.sid
        
        if socket_id not in player_sessions or not player_sessions[socket_id]['username']:
            emit('lobby_error', {'error': 'Username required'})
            return
        
        # Generate secure token for this player
        player_token = secrets.token_urlsafe(16)
        username = player_sessions[socket_id]['username']
        
        # Store token mapping (NOT tied to socket ID)
        player_tokens[player_token] = {
            'username': username,
            'game_id': None,  # Will be set when game starts
            'player_index': None,  # Will be set when game starts
            'used': False  # Track if token has been used
        }
        
        # Generate lobby
        lobby_code = generate_lobby_code()
        lobby = {
            'code': lobby_code,
            'name': data.get('name', 'New Lobby'),
            'host': socket_id,
            'players': [{
                'socketId': socket_id,
                'username': username,
                'isHost': True,
                'isReady': False,
                'token': player_token  # Store token with player
            }],
            'config': {
                'smallBlind': data.get('smallBlind', 5),
                'bigBlind': data.get('bigBlind', 10),
                'startingFunds': data.get('startingFunds', 1000),
                'maxPlayers': data.get('maxPlayers', 8)
            },
            'status': 'waiting'
        }
        
        active_lobbies[lobby_code] = lobby
        player_sessions[socket_id]['lobby_code'] = lobby_code
        
        join_room(f"lobby_{lobby_code}")
        emit('lobby_created', {'lobbyCode': lobby_code, 'lobby': lobby})
        
        logger.info(f"Created lobby {lobby_code} with token for {username}")
    
    @socketio.on('join_lobby')
    def handle_join_lobby(data):
        socket_id = request.sid
        lobby_code = data.get('code', '').strip().upper()
        
        if socket_id not in player_sessions or not player_sessions[socket_id]['username']:
            emit('lobby_error', {'error': 'Username required'})
            return
        
        if lobby_code not in active_lobbies:
            emit('lobby_error', {'error': 'Lobby not found'})
            return
        
        lobby = active_lobbies[lobby_code]
        
        if len(lobby['players']) >= lobby['config']['maxPlayers']:
            emit('lobby_error', {'error': 'Lobby full'})
            return
        
        # Generate secure token for this player
        player_token = secrets.token_urlsafe(16)
        username = player_sessions[socket_id]['username']
        
        # Store token mapping (NOT tied to socket ID)
        player_tokens[player_token] = {
            'username': username,
            'game_id': None,  # Will be set when game starts
            'player_index': None,  # Will be set when game starts
            'used': False  # Track if token has been used
        }
        
        # Add player
        new_player = {
            'socketId': socket_id,
            'username': username,
            'isHost': False,
            'isReady': False,
            'token': player_token  # Store token with player
        }
        
        lobby['players'].append(new_player)
        player_sessions[socket_id]['lobby_code'] = lobby_code
        
        join_room(f"lobby_{lobby_code}")
        emit('lobby_joined', {'lobbyCode': lobby_code, 'lobby': lobby})
        socketio.emit('player_joined', {'player': new_player, 'lobby': lobby}, room=f"lobby_{lobby_code}")
        
        logger.info(f"Player {username} joined lobby {lobby_code} with token")
    
    @socketio.on('leave_lobby')
    def handle_leave_lobby():
        socket_id = request.sid
        lobby_code = player_sessions[socket_id].get('lobby_code')
        
        if not lobby_code or lobby_code not in active_lobbies:
            emit('lobby_error', {'error': 'Not in lobby'})
            return
        
        lobby = active_lobbies[lobby_code]
        lobby['players'] = [p for p in lobby['players'] if p['socketId'] != socket_id]
        
        leave_room(f"lobby_{lobby_code}")
        player_sessions[socket_id]['lobby_code'] = None
        
        emit('lobby_left', {'message': 'Left lobby'})
        socketio.emit('player_left', {'lobby': lobby}, room=f"lobby_{lobby_code}")
        
        # Clean up empty lobby
        if len(lobby['players']) == 0:
            used_codes.discard(lobby_code)
            del active_lobbies[lobby_code]
    
    @socketio.on('toggle_ready')
    def handle_toggle_ready():
        socket_id = request.sid
        lobby_code = player_sessions[socket_id].get('lobby_code')
        
        if not lobby_code or lobby_code not in active_lobbies:
            return
        
        lobby = active_lobbies[lobby_code]
        
        # Find player and toggle ready
        for player in lobby['players']:
            if player['socketId'] == socket_id:
                player['isReady'] = not player['isReady']
                socketio.emit('player_ready_changed', {'lobby': lobby}, room=f"lobby_{lobby_code}")
                break
    
    @socketio.on('update_lobby_config')
    def handle_update_lobby_config(data):
        socket_id = request.sid
        lobby_code = player_sessions[socket_id].get('lobby_code')
        
        if not lobby_code or lobby_code not in active_lobbies:
            return
        
        lobby = active_lobbies[lobby_code]
        
        # Only host can update
        if lobby['host'] != socket_id:
            emit('lobby_error', {'error': 'Only host can update settings'})
            return
        
        # Update config
        config = lobby['config']
        if 'smallBlind' in data:
            config['smallBlind'] = data['smallBlind']
        if 'bigBlind' in data:
            config['bigBlind'] = data['bigBlind']
        if 'startingFunds' in data:
            config['startingFunds'] = data['startingFunds']
        
        socketio.emit('lobby_config_updated', {'lobby': lobby}, room=f"lobby_{lobby_code}")
    
    @socketio.on('start_game')
    def handle_start_game():
        socket_id = request.sid
        logger.info(f"=== START GAME EVENT RECEIVED from {socket_id} ===")
        
        lobby_code = player_sessions[socket_id].get('lobby_code')
        
        if not lobby_code or lobby_code not in active_lobbies:
            logger.error(f"No valid lobby for socket {socket_id}")
            emit('game_error', {'error': 'Not in a valid lobby'})
            return
        
        lobby = active_lobbies[lobby_code]
        logger.info(f"Processing start_game for lobby {lobby_code}")
        
        # Only host can start game
        if lobby['host'] != socket_id:
            logger.error(f"Non-host {socket_id} tried to start game in lobby {lobby_code}")
            emit('game_error', {'error': 'Only host can start game'})
            return
        
        # Check if all players are ready
        if not all(player['isReady'] for player in lobby['players']):
            logger.error(f"Not all players ready in lobby {lobby_code}")
            emit('game_error', {'error': 'All players must be ready'})
            return
        
        # Need at least 2 players
        if len(lobby['players']) < 2:
            logger.error(f"Not enough players in lobby {lobby_code}")
            emit('game_error', {'error': 'Need at least 2 players'})
            return
        
        logger.info(f"All checks passed, creating game for lobby {lobby_code}")
        
        # Create game via C# API
        from game import create_poker_game
        
        game_id = create_poker_game(lobby)
        
        if not game_id:
            logger.error(f"Failed to create game for lobby {lobby_code}")
            emit('game_error', {'error': 'Failed to create game'})
            return
        
        logger.info(f"Game {game_id} created successfully, now updating tokens...")
        
        # IMMEDIATELY update tokens and prepare players (before any transitions)
        logger.info(f"=== UPDATING TOKENS FOR GAME {game_id} ===")
        logger.info(f"Lobby players: {[p['username'] for p in lobby['players']]}")
        logger.info(f"Player tokens before update: {player_tokens}")
        
        game_players = []
        for i, player in enumerate(lobby['players']):
            logger.info(f"Processing player {i}: {player['username']} with token {player['token']}")
            
            # Update token with game info
            if player['token'] in player_tokens:
                player_tokens[player['token']]['game_id'] = game_id
                player_tokens[player['token']]['player_index'] = i
                logger.info(f"✅ Updated token {player['token']} for {player['username']} with game_id={game_id}, player_index={i}")
                logger.info(f"Token after update: {player_tokens[player['token']]}")
            else:
                logger.error(f"❌ Token {player['token']} not found in player_tokens!")
                logger.error(f"Available tokens: {list(player_tokens.keys())}")
            
            game_players.append({
                'username': player['username'],
                'token': player['token'],
                'player_index': i
            })
        
        # Store expected players for this game
        pending_game_players[game_id] = game_players
        logger.info(f"✅ Stored pending players for game {game_id}: {game_players}")
        logger.info(f"All pending games: {pending_game_players}")
        logger.info(f"Player tokens after all updates: {player_tokens}")
        logger.info(f"=== TOKEN UPDATE COMPLETE ===")
        
        # Update lobby status  
        lobby['status'] = 'transitioning'
        lobby['gameId'] = game_id
        
        # Move all players from lobby room to game room
        for player in lobby['players']:
            leave_room(f"lobby_{lobby_code}", sid=player['socketId'])
            join_room(f"game_{game_id}", sid=player['socketId'])
        
        # Notify all players to transition to game room with their tokens
        for player in lobby['players']:
            logger.info(f"Sending transition event to {player['username']} with token {player['token']}")
            socketio.emit('transition_to_game', {
                'gameId': game_id,
                'playerToken': player['token'],  # Send secure token
                'message': 'Game created! Joining game room...'
            }, room=player['socketId'])
        
        logger.info(f"Game {game_id} created for lobby {lobby_code}, players transitioning with tokens")

# Export global state for access from other modules
__all__ = ['active_lobbies', 'player_sessions', 'player_tokens', 'pending_game_players', 'register_lobby_events']