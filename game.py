# game.py - Poker game management
import requests
import logging
from flask_socketio import emit, join_room, leave_room
from flask import request
import os
from abilities import register_ability_events


logger = logging.getLogger(__name__)

# Configuration
CSHARP_API_URL = os.environ.get('CSHARP_API_URL', 'http://localhost:5001')
API_KEY = os.environ.get('POKER_API_KEY', 'poker-game-api-key-2024')
API_TIMEOUT = 30

# Global game state - resets on server restart
active_games = {}

def create_poker_game(lobby_data):
    """
    Create a new poker game via C# API
    Takes lobby data and returns game_id
    """
    try:
        # Build payload from lobby data - match C# API exactly
        payload = {
            "Players": [
                {
                    "Id": i + 1,  # Note: lowercase 'd' in Id
                    "Name": player['username'], 
                    "StartingFunds": int(lobby_data['config']['startingFunds'])
                }
                for i, player in enumerate(lobby_data['players'])
            ],
            "SmallBlind": int(lobby_data['config']['smallBlind']),
            "BigBlind": int(lobby_data['config']['bigBlind'])
        }
        
        logger.info(f"Creating game with payload: {payload}")
        logger.info(f"Using API URL: {CSHARP_API_URL}")
        logger.info(f"Using API Key: {API_KEY[:10]}...")  # Log first 10 chars for security
        
        # Call C# API
        response = requests.post(
            f"{CSHARP_API_URL}/api/game/create", 
            json=payload,
            headers={'X-API-Key': API_KEY},
            timeout=API_TIMEOUT
        )
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Response text: {response.text}")
        
        if response.status_code == 200:
            game_data = response.json()
            game_id = game_data['GameId']
            
            # Store game data
            active_games[game_id] = {
                'gameId': game_id,
                'lobbyCode': lobby_data['code'],
                'players': lobby_data['players'],
                'gameData': game_data,
                'status': 'created',
                'playersJoined': []  # Track who has joined game room
            }
            
            logger.info(f"Game created successfully: {game_id}")
            return game_id
            
        else:
            error_message = response.text
            logger.error(f"Failed to create game: {response.status_code} - {error_message}")
            
            # Try to parse JSON error if available
            try:
                error_json = response.json()
                logger.error(f"Error JSON: {error_json}")
            except:
                pass
                
            return None
            
    except requests.exceptions.Timeout:
        logger.error("C# API timeout during game creation")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to C# API")
        return None
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        return None

def start_poker_game(game_id):
    """
    Start the poker game via C# API
    """
    try:
        logger.info(f"Starting game: {game_id}")
        
        # Call C# API to start game
        response = requests.post(
            f"{CSHARP_API_URL}/api/game/{game_id}/start",
            headers={'X-API-Key': API_KEY},
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            game_state = response.json()
            
            # Update stored game data
            if game_id in active_games:
                active_games[game_id]['gameData'] = game_state
                active_games[game_id]['status'] = 'started'
            
            logger.info(f"Game started successfully: {game_id}")
            return game_state
            
        else:
            logger.error(f"Failed to start game: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error starting game: {e}")
        return None

def register_game_events(socketio):
    """Register game-related WebSocket events"""
    
    # Register ability events
    register_ability_events(socketio)
    logger.info("Abilities module registered successfully")
    
    @socketio.on('join_game')
    def handle_join_game(data):
        """Player joins game room using secure token"""
        socket_id = request.sid
        game_id = data.get('gameId')
        player_token = data.get('playerToken')
        
        logger.info(f"Player {socket_id} attempting to join game {game_id} with token")
        
        # Import token storage from lobby
        from lobby import player_tokens, pending_game_players
        
        logger.info(f"=== TOKEN DEBUGGING ===")
        logger.info(f"Received token: {player_token}")
        logger.info(f"Available tokens: {list(player_tokens.keys())}")
        logger.info(f"Pending players for game {game_id}: {pending_game_players.get(game_id, 'NONE')}")
        
        # Validate token exists and hasn't been used
        if not player_token or player_token not in player_tokens:
            logger.error(f"Invalid token provided by {socket_id}")
            logger.error(f"Token '{player_token}' not found in available tokens")
            emit('game_error', {'error': 'Invalid authentication token'})
            return
        
        token_info = player_tokens[player_token]
        
        # Check if token has already been used
        if token_info.get('used', False):
            logger.error(f"Token {player_token} has already been used")
            emit('game_error', {'error': 'Authentication token already used'})
            return
        
        # Get player info from token
        username = token_info['username']
        expected_game_id = token_info['game_id']
        player_index = token_info['player_index']
        
        logger.info(f"Token validated for {username} (index {player_index}) in game {expected_game_id}")
        
        # Verify token is for this game
        if expected_game_id != game_id:
            logger.error(f"Token game mismatch: expected {expected_game_id}, got {game_id}")
            emit('game_error', {'error': 'Token not valid for this game'})
            return
        
        # Verify game exists
        if not game_id or game_id not in active_games:
            logger.error(f"Game {game_id} not found")
            emit('game_error', {'error': 'Game not found'})
            return
        
        game = active_games[game_id]
        
        # Use the player index from the token (no need to search)
        if player_index is None or player_index >= len(game['players']):
            logger.error(f"Invalid player index {player_index} for game {game_id}")
            emit('game_error', {'error': 'Invalid player index'})
            return
        
        # Mark token as used
        player_tokens[player_token]['used'] = True
        
        # Add player to joined list if not already there
        if socket_id not in game['playersJoined']:
            game['playersJoined'].append(socket_id)
            logger.info(f"Added player {socket_id} ({username}) to game {game_id}")
        
        # Create/update player mapping
        if 'playerMapping' not in game:
            game['playerMapping'] = {}
        
        game['playerMapping'][socket_id] = {
            'username': username,
            'player_index': player_index,
            'token': player_token
        }
        
        logger.info(f"Player mapping created: {username} -> socket {socket_id} -> index {player_index}")
        
        # Join game room
        join_room(f"game_{game_id}")
        
        # Send game room joined confirmation
        emit('game_room_joined', {
            'gameId': game_id,
            'playersJoined': len(game['playersJoined']),
            'totalPlayers': len(game['players']),
            'message': 'Joined game room'
        })
        
        logger.info(f"Player {username} ({socket_id}) joined game room {game_id} ({len(game['playersJoined'])}/{len(game['players'])})")
        
        # Check if all players have joined
        if len(game['playersJoined']) == len(game['players']):
            # All players joined, now start the actual game
            logger.info(f"All players joined game {game_id}, starting game...")
            
            # Start the game via C# API
            game_state = start_poker_game(game_id)
            
            if game_state:
                # Extract the actual game state from the nested response
                if 'GameState' in game_state:
                    actual_game_state = game_state['GameState']
                else:
                    actual_game_state = game_state
                
                game['gameData'] = actual_game_state
                game['status'] = 'started'
                
                logger.info(f"=== DEBUGGING GAME START FOR {game_id} ===")
                logger.info(f"Players in game metadata: {len(game['players'])}")
                logger.info(f"Players joined: {len(game['playersJoined'])}")
                logger.info(f"Players in C# game state: {len(actual_game_state.get('Players', []))}")
                
                # Log all player mappings
                for i, player_info in enumerate(game['players']):
                    logger.info(f"Player {i}: lobby_socket={player_info['socketId']}, username={player_info['username']}")
                
                # Log who actually joined the game room
                for i, joined_socket in enumerate(game['playersJoined']):
                    logger.info(f"Joined {i}: socket={joined_socket}")
                
                # Log C# game state players
                for i, cs_player in enumerate(actual_game_state.get('Players', [])):
                    logger.info(f"C# Player {i}: name={cs_player.get('Name')}, id={cs_player.get('Id')}")
                
                # FIX: Use the player mapping to send correct filtered states
                for socket_id in game['playersJoined']:
                    player_mapping = game['playerMapping'][socket_id]
                    player_index = player_mapping['player_index']
                    username = player_mapping['username']
                    
                    logger.info(f"Processing player: {username} (socket: {socket_id}, index: {player_index})")
                    
                    # Create filtered copy for this specific player
                    import copy
                    filtered_state = copy.deepcopy(actual_game_state)
                    
                    # Hide other players' private information
                    for j, player in enumerate(filtered_state['Players']):
                        if j != player_index:  # Not this player's index
                            logger.info(f"Hiding player {j} data from {username} (player {player_index})")
                            player['HoleCards'] = []
                            player['Abilities'] = []
                            player['AbilityCount'] = 0
                            player['ValidActions'] = []
                            player['ActionContext'] = None
                        else:
                            logger.info(f"Keeping player {j} data for {username}: {len(player.get('HoleCards', []))} cards, {len(player.get('Abilities', []))} abilities")
                    
                    # Send filtered state to this specific player
                    try:
                        socketio.emit('game_started', {
                            'gameId': game_id,
                            'gameState': filtered_state,
                            'message': 'All players joined! Game started!'
                        }, to=socket_id)
                        
                        logger.info(f"✅ Successfully sent filtered game_started to {username} ({socket_id})")
                    except Exception as e:
                        logger.error(f"❌ Failed to send game_started to {username}: {e}")
                
                logger.info(f"=== GAME START COMPLETE FOR {game_id} ===")
                logger.info(f"Game {game_id} started successfully - sent to all players")
            else:
                logger.error(f"Failed to start game {game_id}")
                socketio.emit('game_error', {
                    'error': 'Failed to start game'
                }, room=f"game_{game_id}")
        else:
            # Still waiting for more players
            socketio.emit('waiting_for_players', {
                'playersJoined': len(game['playersJoined']),
                'totalPlayers': len(game['players']),
                'message': f'Waiting for players... ({len(game["playersJoined"])}/{len(game["players"])})'
            }, room=f"game_{game_id}")
    
    @socketio.on('get_game_state')
    def handle_get_game_state(data):
        """Get current game state"""
        game_id = data.get('gameId')
        
        if not game_id or game_id not in active_games:
            emit('game_error', {'error': 'Game not found'})
            return
        
        # For now, return stored game state
        # Later we'll fetch fresh state from C# API
        game_data = active_games[game_id]['gameData']
        emit('game_state_update', {
            'gameId': game_id,
            'gameState': game_data
        })

# Export for use in other modules
__all__ = ['create_poker_game', 'start_poker_game', 'register_game_events', 'active_games']