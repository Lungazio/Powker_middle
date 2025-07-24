# abilities.py - Flask Abilities Management
import requests
import logging
from flask_socketio import emit
from flask import request
import os

logger = logging.getLogger(__name__)

# Configuration
CSHARP_API_URL = os.environ.get('CSHARP_API_URL', 'http://localhost:5001')
API_KEY = os.environ.get('POKER_API_KEY', 'poker-game-api-key-2024')
API_TIMEOUT = 30

def register_ability_events(socketio):
    """Register ability-related WebSocket events"""
    
    @socketio.on('use_ability')
    def handle_use_ability(data):
        """Handle ability usage requests from players"""
        socket_id = request.sid
        game_id = data.get('gameId')
        ability_type = data.get('ability', '').lower()
        
        logger.info(f"Player {socket_id} using ability {ability_type} in game {game_id}")
        
        # Import game state
        from game import active_games
        
        # Validate game exists
        if not game_id or game_id not in active_games:
            emit('ability_error', {'error': 'Game not found'})
            return
        
        game = active_games[game_id]
        
        # Find player using socket mapping
        player_mapping = game.get('playerMapping', {})
        if socket_id not in player_mapping:
            emit('ability_error', {'error': 'Player not found in game'})
            return
        
        player_info = player_mapping[socket_id]
        player_index = player_info['player_index']
        username = player_info['username']
        
        # Call C# API based on ability type
        try:
            if ability_type == 'peek':
                handle_peek_ability(socketio, game_id, player_index, data)
            elif ability_type == 'burn':
                handle_burn_ability(socketio, game_id, player_index, data)  # FIXED: Added data parameter
            elif ability_type == 'manifest':
                handle_manifest_ability(socketio, game_id, player_index, data)
            elif ability_type == 'trashman':
                handle_trashman_ability(socketio, game_id, player_index, data)
            elif ability_type == 'deadman':
                handle_deadman_ability(socketio, game_id, player_index, data)  # FIXED: Added data parameter
            elif ability_type == 'chaos':
                handle_chaos_ability(socketio, game_id, player_index, data)  # FIXED: Added data parameter
            elif ability_type == 'yoink':
                handle_yoink_ability(socketio, game_id, player_index, data)
            else:
                emit('ability_error', {'error': f'Unknown ability: {ability_type}'})
                
        except Exception as e:
            logger.error(f"Error processing ability {ability_type}: {e}")
            emit('ability_error', {'error': 'Failed to process ability'})
    
    @socketio.on('cancel_ability')
    def handle_cancel_ability(data):
        """Handle ability cancellation"""
        socket_id = request.sid
        game_id = data.get('gameId')
        
        logger.info(f"Player {socket_id} cancelling ability in game {game_id}")
        
        # For now, just acknowledge cancellation
        # In a full implementation, you'd call the C# API to cancel pending choices
        emit('ability_cancelled', {'message': 'Ability cancelled'})

def handle_peek_ability(socketio, game_id, player_index, data):
    """Handle peek ability - requires target player and card index"""
    target_player_id = data.get('targetPlayerId')
    card_index = data.get('cardIndex')
    
    if target_player_id is None or card_index is None:
        # Need to request choice from player
        send_peek_choice_request(socketio, game_id, player_index)
        return
    
    # Make API call with choices
    payload = {
        'playerId': player_index + 1,  # C# API uses 1-based indexing
        'abilityType': 'peek',
        'targetPlayerId': target_player_id,
        'cardIndex': card_index
    }
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            # Send error to requesting player only
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Peek failed'))

def handle_burn_ability(socketio, game_id, player_index, data):
    """Handle burn ability - requires reveal choice (suit or rank)"""
    reveal_suit = data.get('revealSuit')
    
    if reveal_suit is None:
        # Need to request choice from player
        send_burn_choice_request(socketio, game_id, player_index)
        return
    
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'burn',
        'revealSuit': reveal_suit
    }
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Burn failed'))

def send_burn_choice_request(socketio, game_id, player_index):
    """Send burn choice request to player"""
    choice_data = {
        'abilityUsed': 'burn',
        'choiceRequired': True,
        'step': 1,
        'revealOptions': [
            {'value': True, 'name': 'Reveal Suit'},
            {'value': False, 'name': 'Reveal Rank'}
        ],
        'instructions': 'Choose what to reveal when burning a card',
        'message': 'Burn: Choose suit or rank to reveal'
    }
    
    send_ability_choice_to_player(socketio, game_id, player_index, choice_data)

def handle_manifest_ability(socketio, game_id, player_index, data):
    """Handle manifest ability - may require card choice"""
    discard_index = data.get('discardIndex')
    drawn_card = data.get('drawnCard')
    drawn_card_suit = data.get('drawnCardSuit')
    
    # Always start by calling the API to get the drawn card
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'manifest'
    }
    
    # If we have a choice, include it
    if discard_index is not None:
        payload['discardIndex'] = discard_index
        if drawn_card is not None:
            payload['drawnCard'] = drawn_card
        if drawn_card_suit is not None:
            payload['drawnCardSuit'] = drawn_card_suit
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('ChoiceRequired'):
            # API returned choice options - send to player
            send_manifest_choice_to_player(socketio, game_id, player_index, response)
        elif response.get('Success'):
            # Manifest completed
            broadcast_ability_result(socketio, game_id, response)
        else:
            # Error occurred
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Manifest failed'))

def send_manifest_choice_to_player(socketio, game_id, player_index, api_response):
    """Send manifest card choice to player using API response"""
    available_cards = api_response.get('AvailableCards', [])
    drawn_card = api_response.get('DrawnCard', {})
    
    choice_data = {
        'abilityUsed': 'manifest',
        'choiceRequired': True,
        'step': 1,
        'availableCards': [
            {
                'index': card.get('Index', i),
                'card': card.get('Card', ''),
                'rank': card.get('Rank', ''),
                'suit': card.get('Suit', ''),
                'isDrawnCard': card.get('IsDrawnCard', False),
                'cardType': card.get('CardType', '')
            }
            for i, card in enumerate(available_cards)
        ],
        'drawnCard': drawn_card,
        'instructions': api_response.get('Instructions', 'Select one card to discard'),
        'message': 'Manifest: Choose which card to discard'
    }
    
    send_ability_choice_to_player(socketio, game_id, player_index, choice_data)

def handle_trashman_ability(socketio, game_id, player_index, data):
    """Handle trashman ability - three-step process"""
    burnt_card_index = data.get('burntCardIndex')
    hole_card_index = data.get('holeCardIndex')
    
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'trashman'
    }
    
    # Add parameters based on what we have
    if burnt_card_index is not None:
        payload['burntCardIndex'] = burnt_card_index
    if hole_card_index is not None:
        payload['holeCardIndex'] = hole_card_index
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('ChoiceRequired'):
            send_trashman_choice_to_player(socketio, game_id, player_index, response)
        elif response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Trashman failed'))

def send_trashman_choice_to_player(socketio, game_id, player_index, api_response):
    """Send trashman choice to player using API response"""
    step = api_response.get('Step', 1)
    
    if step == 1:
        # Step 1: Choose burnt card to retrieve
        available_burnt_cards = api_response.get('AvailableBurntCards', [])
        current_hole_cards = api_response.get('CurrentHoleCards', [])
        
        choice_data = {
            'abilityUsed': 'trashman',
            'choiceRequired': True,
            'step': 1,
            'availableBurntCards': [
                {
                    'index': card.get('Index', i),
                    'card': card.get('Card', ''),
                    'rank': card.get('Rank', ''),
                    'suit': card.get('Suit', '')
                }
                for i, card in enumerate(available_burnt_cards)
            ],
            'currentHoleCards': current_hole_cards,
            'instructions': api_response.get('Instructions', 'Select which burnt card to retrieve'),
            'message': 'Trashman Step 1: Choose burnt card to retrieve'
        }
    else:
        # Step 2: Choose hole card to discard
        chosen_burnt_card = api_response.get('ChosenBurntCard', {})
        available_hole_cards = api_response.get('AvailableHoleCards', [])
        
        choice_data = {
            'abilityUsed': 'trashman',
            'choiceRequired': True,
            'step': 2,
            'chosenBurntCard': chosen_burnt_card,
            'availableHoleCards': [
                {
                    'index': card.get('Index', i),
                    'card': card.get('Card', ''),
                    'rank': card.get('Rank', ''),
                    'suit': card.get('Suit', '')
                }
                for i, card in enumerate(available_hole_cards)
            ],
            'instructions': api_response.get('Instructions', 'Select which hole card to discard'),
            'message': f'Trashman Step 2: Choose hole card to discard (retrieving {chosen_burnt_card.get("Card", "card")})'
        }
    
    send_ability_choice_to_player(socketio, game_id, player_index, choice_data)

def handle_deadman_ability(socketio, game_id, player_index, data):
    """Handle deadman ability - no choices needed"""
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'deadman'
    }
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Deadman failed'))

def handle_chaos_ability(socketio, game_id, player_index, data):
    """Handle chaos ability - no choices needed"""
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'chaos'
    }
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Chaos failed'))

def handle_yoink_ability(socketio, game_id, player_index, data):
    """Handle yoink ability - requires hole card and board card choice"""
    card_index = data.get('cardIndex')  # hole card index (renamed from holeCardIndex)
    target_player_id = data.get('targetPlayerId')  # board card index (renamed from boardCardIndex)
    
    if card_index is None or target_player_id is None:
        # Need to request choices
        send_yoink_choice_request(socketio, game_id, player_index)
        return
    
    payload = {
        'playerId': player_index + 1,
        'abilityType': 'yoink',
        'cardIndex': card_index,  # hole card index
        'targetPlayerId': target_player_id  # board card index (API uses this field name)
    }
    
    response = call_csharp_ability_api(game_id, payload)
    if response:
        if response.get('ChoiceRequired'):
            send_yoink_choice_to_player(socketio, game_id, player_index, response)
        elif response.get('Success'):
            broadcast_ability_result(socketio, game_id, response)
        else:
            send_ability_error_to_player(socketio, game_id, player_index, response.get('error', 'Yoink failed'))

def call_csharp_ability_api(game_id, payload):
    """Make API call to C# backend for ability"""
    try:
        logger.info(f"Calling C# API for ability: {payload}")
        
        response = requests.post(
            f"{CSHARP_API_URL}/api/game/{game_id}/abilities/use",
            json=payload,
            headers={'X-API-Key': API_KEY},
            timeout=API_TIMEOUT
        )
        
        logger.info(f"C# API response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Ability result: {result}")
            return result
        else:
            logger.error(f"C# API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("C# API timeout during ability call")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to C# API for ability")
        return None
    except Exception as e:
        logger.error(f"Error calling C# API for ability: {e}")
        return None

def broadcast_ability_result(socketio, game_id, response):
    """Broadcast ability result to all players in game"""
    from game import active_games
    from game_filter import send_filtered_game_state
    
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    ability_used = response.get('AbilityUsed', '').lower()
    player_name = response.get('PlayerName', '')
    
    # Update stored game state if provided
    if 'GameState' in response:
        game['gameData'] = response['GameState']
    
    # Handle different privacy levels for different abilities
    if ability_used == 'peek':
        # PEEK: Show card only to the player who peeked, announcement to everyone else
        peek_result = response.get('Result', {})
        peeked_card = peek_result.get('PeekedCard', 'Unknown Card')
        target_player_name = get_player_name_by_id(game, peek_result.get('TargetPlayerId'))
        card_number = peek_result.get('CardIndex', 0) + 1  # Convert to 1-based
        
        # Message with card details (only for the peeker)
        private_message = f"{player_name} peeked at {target_player_name}'s card #{card_number}: {peeked_card}"
        
        # Public announcement (for everyone else)
        public_message = f"{player_name} peeked at {target_player_name}'s card #{card_number}"
        
        send_private_ability_result(socketio, game_id, response, private_message, public_message)
        
    elif ability_used in ['manifest', 'burn', 'trashman', 'deadman']:
        # PRIVATE ABILITIES: Show details only to the player who used it, announcement to others
        full_message = response.get('Message', '')
        
        # Create public announcement without revealing private details
        if ability_used == 'manifest':
            public_message = f"{player_name} used Manifest ability"
        elif ability_used == 'burn':
            public_message = f"{player_name} used Burn ability"
        elif ability_used == 'trashman':
            public_message = f"{player_name} used Trashman ability"
        elif ability_used == 'deadman':
            public_message = f"{player_name} used Deadman ability"
        
        send_private_ability_result(socketio, game_id, response, full_message, public_message)
        
    elif ability_used == 'chaos':
        # CHAOS: Show announcement only (no card details to anyone)
        public_message = f"{player_name} used Chaos ability - all active players' cards have been shuffled!"
        
        # Send same message to everyone
        socketio.emit('ability_result', {
            'success': response.get('Success', False),
            'message': public_message,
            'abilityUsed': ability_used,
            'playerName': player_name,
            'result': {},  # No private details
            'summary': public_message
        }, room=f"game_{game_id}")
        
    elif ability_used == 'yoink':
        # YOINK: Show card swap details to everyone
        yoink_result = response.get('Result', {})
        hole_card = yoink_result.get('HoleCardSwapped', 'Unknown')
        board_card = yoink_result.get('BoardCardSwapped', 'Unknown')
        
        public_message = f"{player_name} used Yoink - swapped {hole_card} from hand with {board_card} from board"
        
        # Send same message to everyone
        socketio.emit('ability_result', {
            'success': response.get('Success', False),
            'message': public_message,
            'abilityUsed': ability_used,
            'playerName': player_name,
            'result': yoink_result,
            'summary': public_message
        }, room=f"game_{game_id}")
        
    else:
        # DEFAULT: Send full message to everyone (fallback)
        socketio.emit('ability_result', {
            'success': response.get('Success', False),
            'message': response.get('Message', ''),
            'abilityUsed': ability_used,
            'playerName': player_name,
            'result': response.get('Result', {}),
            'summary': response.get('Summary', '')
        }, room=f"game_{game_id}")
    
    # Send filtered game state if updated
    if 'GameState' in response:
        send_filtered_game_state(
            socketio, 
            'game_state_update', 
            game_id, 
            response['GameState'], 
            game,
            f"Game updated after {ability_used} ability"
        )

def send_private_ability_result(socketio, game_id, response, private_message, public_message):
    """Send different messages to the ability user vs other players"""
    from game import active_games
    
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    ability_user_id = response.get('PlayerId')
    ability_used = response.get('AbilityUsed', '').lower()
    player_name = response.get('PlayerName', '')
    
    # Find the socket ID of the player who used the ability
    ability_user_socket = None
    for socket_id, mapping in game.get('playerMapping', {}).items():
        if mapping['player_index'] + 1 == ability_user_id:  # Convert to 1-based indexing
            ability_user_socket = socket_id
            break
    
    # Send detailed message to the ability user
    if ability_user_socket:
        socketio.emit('ability_result', {
            'success': response.get('Success', False),
            'message': private_message,
            'abilityUsed': ability_used,
            'playerName': player_name,
            'result': response.get('Result', {}),
            'summary': private_message,
            'isPrivate': True
        }, room=ability_user_socket)
    
    # Send public announcement to everyone else
    for socket_id in game.get('playersJoined', []):
        if socket_id != ability_user_socket:
            socketio.emit('ability_result', {
                'success': response.get('Success', False),
                'message': public_message,
                'abilityUsed': ability_used,
                'playerName': player_name,
                'result': {},  # No private details for others
                'summary': public_message,
                'isPrivate': False
            }, room=socket_id)

def get_player_name_by_id(game, player_id):
    """Get player name by their ID from game state"""
    game_state = game.get('gameData', {})
    if 'GameState' in game_state:
        actual_game_state = game_state['GameState']
    else:
        actual_game_state = game_state
    
    for player in actual_game_state.get('Players', []):
        if player.get('Id') == player_id:
            return player.get('Name', f'Player {player_id}')
    
    return f'Player {player_id}'

def send_ability_choice_to_player(socketio, game_id, player_index, response):
    """Send choice request to specific player"""
    from game import active_games
    
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    
    # Find the socket ID for this player
    target_socket_id = None
    for socket_id, mapping in game.get('playerMapping', {}).items():
        if mapping['player_index'] == player_index:
            target_socket_id = socket_id
            break
    
    if target_socket_id:
        socketio.emit('ability_choice_required', response, room=target_socket_id)
        logger.info(f"Sent choice request to player {player_index} in game {game_id}")

def send_peek_choice_request(socketio, game_id, player_index):
    """Send peek choice request to player"""
    from game import active_games
    
    if game_id not in active_games:
        return
        
    game = active_games[game_id]
    game_state = game.get('gameData', {})
    
    # Get available players (not folded, not self)
    available_players = []
    for i, player in enumerate(game_state.get('Players', [])):
        if (i != player_index and 
            not player.get('IsFolded', False)):
            available_players.append({
                'id': player.get('Id', i + 1),
                'name': player.get('Name', f'Player {i + 1}'),
                'balance': player.get('Balance', 0)
            })
    
    if not available_players:
        send_ability_error_to_player(socketio, game_id, player_index, "No valid players to peek at")
        return
    
    choice_data = {
        'abilityUsed': 'peek',
        'choiceRequired': True,
        'step': 1,
        'availablePlayers': available_players,
        'cardOptions': [
            {'index': 0, 'name': 'First Card'},
            {'index': 1, 'name': 'Second Card'}
        ],
        'instructions': 'Choose a player and which card to peek at',
        'message': 'Select target player and card for Peek ability'
    }
    
    send_ability_choice_to_player(socketio, game_id, player_index, choice_data)

def send_yoink_choice_request(socketio, game_id, player_index):
    """Send yoink choice request to player"""
    from game import active_games
    
    if game_id not in active_games:
        return
        
    game = active_games[game_id]
    game_state = game.get('gameData', {})
    
    # Get player's hole cards and board cards
    players = game_state.get('Players', [])
    if player_index >= len(players):
        send_ability_error_to_player(socketio, game_id, player_index, "Player not found")
        return
        
    player_data = players[player_index]
    hole_cards = player_data.get('HoleCards', [])
    board_cards = game_state.get('Board', [])
    
    if not hole_cards:
        send_ability_error_to_player(socketio, game_id, player_index, "No hole cards available")
        return
        
    if not board_cards:
        send_ability_error_to_player(socketio, game_id, player_index, "No board cards available to yoink")
        return
    
    choice_data = {
        'abilityUsed': 'yoink',
        'choiceRequired': True,
        'step': 1,
        'availableHoleCards': [
            {'index': i, 'card': card, 'rank': card.split(' of ')[0], 'suit': card.split(' of ')[1]} 
            for i, card in enumerate(hole_cards)
        ],
        'availableBoardCards': [
            {'index': i, 'card': card, 'rank': card.split(' of ')[0], 'suit': card.split(' of ')[1]} 
            for i, card in enumerate(board_cards)
        ],
        'instructions': 'Choose one hole card and one board card to swap',
        'message': 'Select cards to swap with Yoink ability',
        'note': 'API uses cardIndex for hole card and targetPlayerId for board card index'
    }
    
    send_ability_choice_to_player(socketio, game_id, player_index, choice_data)

def send_ability_error_to_player(socketio, game_id, player_index, error_message):
    """Send error message to specific player"""
    from game import active_games
    
    if game_id not in active_games:
        return
    
    game = active_games[game_id]
    
    # Find the socket ID for this player
    target_socket_id = None
    for socket_id, mapping in game.get('playerMapping', {}).items():
        if mapping['player_index'] == player_index:
            target_socket_id = socket_id
            break
    
    if target_socket_id:
        socketio.emit('ability_error', {'error': error_message}, room=target_socket_id)
        logger.info(f"Sent ability error to player {player_index}: {error_message}")

# Export for use in other modules
__all__ = ['register_ability_events']