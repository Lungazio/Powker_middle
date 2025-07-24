// Game Room Client
class GameRoomClient {
    constructor() {
        this.socket = null;
        this.gameId = null;
        this.gameState = null;
        this.abilitySelectionManager = null;
        
        this.init();
    }

    init() {
        // Get game ID from URL or page
        const gameIdElement = document.getElementById('current-game-id');
        this.gameId = gameIdElement.textContent;
        
        if (!this.gameId || this.gameId === '-----') {
            this.addActionLog('Error: No game ID provided', 'system');
            return;
        }

        this.initializeSocket();
        this.bindEvents();
        
        // Initialize ability selection manager
        this.abilitySelectionManager = new AbilitySelectionManager(this);
        
        this.joinGame();
    }

    // Socket Connection
    initializeSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateConnectionStatus('connected', 'Connected');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus('disconnected', 'Disconnected');
            this.addActionLog('Connection lost. Please refresh the page.', 'system');
        });

        this.socket.on('connect_error', () => {
            this.updateConnectionStatus('disconnected', 'Connection Error');
        });

        this.registerGameEvents();
    }

    registerGameEvents() {
        // Game room events
        this.socket.on('game_room_joined', (data) => {
            console.log('Game room joined:', data);
            this.addActionLog(`Joined game room (${data.playersJoined}/${data.totalPlayers} players)`, 'system');
            
            // Now safe to clear token
            localStorage.removeItem('playerToken');
            console.log('Token cleared after successful join');
        });

        this.socket.on('waiting_for_players', (data) => {
            console.log('Waiting for players:', data);
            this.addActionLog(data.message, 'system');
        });

        this.socket.on('game_started', (data) => {
            console.log('Game started event received:', data);
            this.addActionLog('Game started!', 'important');
            this.gameState = data.gameState;
            this.updateGameDisplay();
        });

        this.socket.on('game_state_update', (data) => {
            this.gameState = data.gameState;
            this.updateGameDisplay();
        });

        this.socket.on('game_error', (data) => {
            this.addActionLog(`Error: ${data.error}`, 'system');
        });

        // Player action events
        this.socket.on('player_action_result', (data) => {
            this.addActionLog(`${data.PlayerAction.PlayerName} ${data.PlayerAction.Action.toLowerCase()}${data.PlayerAction.Amount ? ` $${data.PlayerAction.Amount}` : ''}`, 'player-action');
            if (data.GameState) {
                this.gameState = data.GameState;
                this.updateGameDisplay();
            }
        });

        // Ability events (handled by Flask backend)
        this.socket.on('ability_result', (data) => {
            this.addActionLog(data.message, 'player-action');
            // Game state will be updated via separate game_state_update event
        });

        this.socket.on('ability_choice_required', (data) => {
            this.abilitySelectionManager.handleAbilityChoiceRequired(data);
        });

        this.socket.on('ability_error', (data) => {
            this.addActionLog(`Ability error: ${data.error}`, 'system');
        });

        this.socket.on('ability_cancelled', (data) => {
            this.addActionLog(data.message, 'system');
        });
    }

    // Socket Actions
    joinGame() {
        this.addActionLog('Joining game room...', 'system');
        console.log('Emitting join_game for gameId:', this.gameId);
        
        // Get secure token from localStorage
        const playerToken = localStorage.getItem('playerToken');
        console.log('Retrieved token from localStorage:', playerToken ? 'TOKEN_EXISTS' : 'NO_TOKEN');
        
        if (!playerToken) {
            this.addActionLog('Error: No authentication token found', 'system');
            console.log('localStorage contents:', localStorage);
            return;
        }
        
        this.socket.emit('join_game', { 
            gameId: this.gameId,
            playerToken: playerToken
        });
        
        // Don't clear token immediately - wait for successful join
        console.log('Sent join_game with token to backend');
    }

    leaveGame() {
        if (confirm('Are you sure you want to leave the game?')) {
            // Redirect back to lobby
            window.location.href = '/';
        }
    }

    // Event Binding
    bindEvents() {
        document.getElementById('leave-game-btn').addEventListener('click', () => {
            this.leaveGame();
        });
    }

    // UI Updates
    updateConnectionStatus(status, text) {
        const statusEl = document.getElementById('connection-status');
        const statusText = document.getElementById('status-text');
        
        statusEl.className = `connection-status ${status}`;
        statusText.textContent = text;
    }

    updateGameDisplay() {
        if (!this.gameState) {
            console.log('No game state to display');
            return;
        }

        console.log('Updating game display with state:', this.gameState);

        // Update game info
        document.getElementById('current-phase').textContent = this.gameState.CurrentPhase || '-----';
        document.getElementById('current-pot').textContent = this.gameState.Pot || '0';
        
        // Update current bet display
        const currentBet = this.gameState.TurnManager ? this.gameState.TurnManager.CurrentBet : 0;
        document.getElementById('current-bet-amount').textContent = currentBet;

        // Update turn indicator and player list
        this.updateTurnIndicator();

        // Update player's hole cards
        this.updateHoleCards();

        // Update community board
        this.updateBoardCards();

        // Update abilities
        this.updateAbilities();

        // Add game state info to log
        this.addActionLog(`Phase: ${this.gameState.CurrentPhase}, Pot: ${this.gameState.Pot}, Current Player: ${this.gameState.CurrentPlayer || 'None'}`, 'system');
    }

    updateTurnIndicator() {
        const turnListContainer = document.getElementById('players-turn-list');
        
        if (!this.gameState || !this.gameState.Players) {
            turnListContainer.innerHTML = '<div class="no-players">No players available</div>';
            return;
        }

        console.log('Updating turn indicator with players:', this.gameState.Players);

        turnListContainer.innerHTML = '';

        this.gameState.Players.forEach((player, index) => {
            const playerItem = document.createElement('div');
            playerItem.className = 'player-turn-item';

            // Determine player status classes
            if (player.IsMyTurn) {
                playerItem.classList.add('current-turn');
            } else if (player.IsFolded) {
                playerItem.classList.add('folded');
            } else if (player.IsAllIn) {
                playerItem.classList.add('all-in');
            } else if (player.HasActedThisRound) {
                playerItem.classList.add('acted');
            }

            // Determine turn status text
            let statusText = '';
            if (player.IsMyTurn) {
                statusText = 'Current Turn';
            } else if (player.IsFolded) {
                statusText = 'Folded';
            } else if (player.IsAllIn) {
                statusText = 'All In';
            } else if (player.HasActedThisRound) {
                statusText = 'Waiting';
            } else {
                statusText = 'To Act';
            }

            // Get last action (this would need to be tracked from previous actions)
            let lastAction = '';
            if (player.HasActedThisRound && !player.IsFolded && !player.IsAllIn) {
                // Determine action based on bet amount
                if (player.CurrentBet === 0) {
                    lastAction = '<div class="player-action check">Check</div>';
                } else {
                    // This is simplified - in reality you'd track the specific action
                    lastAction = '<div class="player-action call">Call</div>';
                }
            } else if (player.IsFolded) {
                lastAction = '<div class="player-action fold">Fold</div>';
            } else if (player.IsAllIn) {
                lastAction = '<div class="player-action all-in">All In</div>';
            }

            // Format the player name with funds in parentheses
            const playerNameWithFunds = `${player.Name} ($${player.Balance})`;

            playerItem.innerHTML = `
                <div class="player-turn-info">
                    <div class="player-turn-name">${playerNameWithFunds}</div>
                    <div class="player-turn-status">${statusText}</div>
                </div>
                <div class="player-turn-stats">
                    <div class="player-bet">Bet: $${player.CurrentBet}</div>
                    ${lastAction}
                </div>
            `;

            turnListContainer.appendChild(playerItem);
        });
    }

    // Helper function to parse card and get suit info
    parseCard(cardString) {
        // Handle different card formats like "3 of Clubs", "King of Hearts", etc.
        const parts = cardString.toLowerCase().split(' of ');
        if (parts.length !== 2) {
            return { display: cardString, isRed: false }; // Fallback
        }
        
        const rank = parts[0];
        const suit = parts[1];
        
        // Convert rank to short form
        let shortRank;
        switch(rank) {
            case 'ace': shortRank = 'A'; break;
            case 'king': shortRank = 'K'; break;
            case 'queen': shortRank = 'Q'; break;
            case 'jack': shortRank = 'J'; break;
            default: shortRank = rank; break;
        }
        
        // Get suit symbol and color
        let suitSymbol, isRed;
        switch(suit) {
            case 'hearts': suitSymbol = '♥'; isRed = true; break;
            case 'diamonds': suitSymbol = '♦'; isRed = true; break;
            case 'clubs': suitSymbol = '♣'; isRed = false; break;
            case 'spades': suitSymbol = '♠'; isRed = false; break;
            default: suitSymbol = suit[0].toUpperCase(); isRed = false; break;
        }
        
        return {
            display: `${shortRank}${suitSymbol}`,
            isRed: isRed
        };
    }

    updateHoleCards() {
        const holeCardsContainer = document.getElementById('hole-cards');
        
        if (!this.gameState || !this.gameState.Players) {
            console.log('No game state or players available');
            return;
        }
        
        // Find the player with hole cards (should be only me after filtering)
        const myPlayer = this.gameState.Players.find(p => p.HoleCards && p.HoleCards.length > 0);
        
        if (myPlayer && myPlayer.HoleCards && myPlayer.HoleCards.length > 0) {
            console.log('Updating my hole cards:', myPlayer.HoleCards);
            holeCardsContainer.innerHTML = '';
            myPlayer.HoleCards.forEach((card, index) => {
                const cardInfo = this.parseCard(card);
                const cardEl = document.createElement('div');
                cardEl.className = `card-placeholder revealed ${cardInfo.isRed ? 'red-suit' : 'black-suit'}`;
                cardEl.textContent = cardInfo.display;
                holeCardsContainer.appendChild(cardEl);
            });
        } else {
            console.log('No hole cards available for me');
            // Default placeholder
            holeCardsContainer.innerHTML = `
                <div class="card-placeholder">Card 1</div>
                <div class="card-placeholder">Card 2</div>
            `;
        }
    }

    updateBoardCards() {
        const boardContainer = document.getElementById('board-cards');
        
        if (this.gameState.Board && this.gameState.Board.length > 0) {
            boardContainer.innerHTML = '';
            
            // Add revealed community cards
            this.gameState.Board.forEach((card, index) => {
                const cardInfo = this.parseCard(card);
                const cardEl = document.createElement('div');
                cardEl.className = `card-placeholder revealed ${cardInfo.isRed ? 'red-suit' : 'black-suit'}`;
                cardEl.textContent = cardInfo.display;
                boardContainer.appendChild(cardEl);
            });
            
            // Add placeholder for remaining cards
            const totalCards = 5;
            for (let i = this.gameState.Board.length; i < totalCards; i++) {
                const cardEl = document.createElement('div');
                cardEl.className = 'card-placeholder hidden';
                const names = ['Flop 1', 'Flop 2', 'Flop 3', 'Turn', 'River'];
                cardEl.textContent = names[i];
                boardContainer.appendChild(cardEl);
            }
        } else {
            // Default placeholders
            boardContainer.innerHTML = `
                <div class="card-placeholder hidden">Flop 1</div>
                <div class="card-placeholder hidden">Flop 2</div>
                <div class="card-placeholder hidden">Flop 3</div>
                <div class="card-placeholder hidden">Turn</div>
                <div class="card-placeholder hidden">River</div>
            `;
        }
    }

    updateAbilities() {
        const abilitiesContainer = document.getElementById('ability-cards');
        
        if (!this.gameState || !this.gameState.Players) {
            abilitiesContainer.innerHTML = '<div class="no-abilities">No game state available</div>';
            return;
        }
        
        // Find the player with abilities (should be only me after filtering)
        const myPlayer = this.gameState.Players.find(p => p.Abilities && p.Abilities.length > 0);
        
        if (myPlayer && myPlayer.Abilities && myPlayer.Abilities.length > 0) {
            console.log('Updating my abilities:', myPlayer.Abilities);
            abilitiesContainer.innerHTML = '';
            
            myPlayer.Abilities.forEach(ability => {
                const abilityEl = document.createElement('button');
                abilityEl.className = 'ability-card';
                abilityEl.innerHTML = `
                    <div class="ability-name">${ability.Name}</div>
                    <div class="ability-description">${ability.Description}</div>
                `;
                
                abilityEl.addEventListener('click', () => {
                    this.useAbility(ability.Type);
                });
                
                // Add ability type as data attribute for CSS styling
                abilityEl.setAttribute('data-ability', ability.Type.toLowerCase());
                
                abilitiesContainer.appendChild(abilityEl);
            });
        } else {
            abilitiesContainer.innerHTML = '<div class="no-abilities">No abilities available</div>';
        }
    }

    useAbility(abilityType) {
        this.addActionLog(`Using ${abilityType} ability...`, 'player-action');
        
        // Send ability request to Flask backend (no parameters initially)
        this.socket.emit('use_ability', {
            gameId: this.gameId,
            ability: abilityType.toLowerCase()
        });
    }

    addActionLog(message, type = 'system') {
        const actionsLog = document.getElementById('actions-log');
        const actionItem = document.createElement('div');
        actionItem.className = `action-item ${type}`;
        
        // Add timestamp
        const timestamp = new Date().toLocaleTimeString();
        actionItem.textContent = `[${timestamp}] ${message}`;
        
        actionsLog.appendChild(actionItem);
        
        // Auto-scroll to bottom
        actionsLog.scrollTop = actionsLog.scrollHeight;
        
        // Keep only last 20 messages (reduced from 50)
        const items = actionsLog.querySelectorAll('.action-item');
        if (items.length > 20) {
            items[0].remove();
        }
    }
}

// Initialize the game room client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.gameRoomClient = new GameRoomClient();
});