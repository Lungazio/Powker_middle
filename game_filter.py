# game_filter.py - Filter game state for individual players
import copy
import logging

logger = logging.getLogger(__name__)

def filter_game_state_for_player(game_state, player_socket_id, game_metadata):
    """
    Filter game state to only show private information for the specific player
    
    Args:
        game_state: Full game state from C# API
        player_socket_id: Socket ID of the player requesting the state
        game_metadata: Game metadata containing player mappings
        
    Returns:
        Filtered game state with only the player's private information
    """
    try:
        # Create a deep copy to avoid modifying the original
        filtered_state = copy.deepcopy(game_state)
        
        # Find which player this socket represents
        player_index = None
        for i, player_info in enumerate(game_metadata['players']):
            if player_info['socketId'] == player_socket_id:
                player_index = i
                break
        
        if player_index is None:
            logger.warning(f"Could not find player for socket {player_socket_id}")
            return filtered_state
        
        # Filter players - hide other players' private info
        for i, player in enumerate(filtered_state['Players']):
            if i != player_index:
                # Hide other players' private information
                player['HoleCards'] = []  # Empty for other players
                player['Abilities'] = []  # Empty for other players
                player['AbilityCount'] = 0
                player['ValidActions'] = []  # Only current player needs actions
                player['ActionContext'] = None
                # Keep public info like balance, bets, turn status, etc.
        
        logger.info(f"Filtered game state for player {player_socket_id} (index {player_index})")
        return filtered_state
        
    except Exception as e:
        logger.error(f"Error filtering game state: {e}")
        return game_state  # Return original on error

def send_filtered_game_state(socketio, event_name, game_id, game_state, game_metadata, message=None):
    """
    Send filtered game state to each player individually
    
    Args:
        socketio: SocketIO instance
        event_name: Name of the event to emit (e.g., 'game_started', 'game_state_update')
        game_id: Game ID
        game_state: Full game state from C# API
        game_metadata: Game metadata containing player mappings
        message: Optional message to include
    """
    try:
        # Send personalized game state to each player
        for i, player_info in enumerate(game_metadata['players']):
            player_socket_id = player_info['socketId']
            
            # Filter game state for this specific player
            filtered_state = filter_game_state_for_player(game_state, player_socket_id, game_metadata)
            
            # Build event payload
            payload = {
                'gameId': game_id,
                'gameState': filtered_state
            }
            
            if message:
                payload['message'] = message
            
            # Send to specific player only
            socketio.emit(event_name, payload, room=player_socket_id)
            
            logger.info(f"Sent {event_name} to player {player_socket_id} (index {i})")
        
        logger.info(f"Sent filtered {event_name} to all {len(game_metadata['players'])} players")
        
    except Exception as e:
        logger.error(f"Error sending filtered game state: {e}")
        # Fallback: send to whole room without filtering
        socketio.emit(event_name, {
            'gameId': game_id,
            'gameState': game_state,
            'message': message or 'Game state update'
        }, room=f"game_{game_id}")

# Helper function to identify player by socket ID
def get_player_index_by_socket(socket_id, game_metadata):
    """
    Get the player index (0, 1, 2, etc.) for a given socket ID
    """
    for i, player_info in enumerate(game_metadata['players']):
        if player_info['socketId'] == socket_id:
            return i
    return None

# Helper function to check if player can see information
def can_player_see_cards(viewing_player_index, target_player_index):
    """
    Determine if a player can see another player's cards
    Currently only allows seeing own cards, but can be extended for special abilities
    """
    return viewing_player_index == target_player_index

# Export functions
__all__ = [
    'filter_game_state_for_player',
    'send_filtered_game_state', 
    'get_player_index_by_socket',
    'can_player_see_cards'
]