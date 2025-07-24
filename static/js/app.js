// Poker Game Client
class PokerClient {
    constructor() {
        this.socket = null;
        this.username = '';
        this.currentLobby = null;
        this.isHost = false;
        this.isReady = false;
        
        this.init();
    }

    init() {
        this.initializeSocket();
        this.bindEvents();
        this.showScreen('username-screen');
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
            this.showMessage('Connection lost. Please refresh the page.', 'error');
        });

        this.socket.on('connect_error', () => {
            this.updateConnectionStatus('disconnected', 'Connection Error');
        });

        // Register event listeners
        this.registerSocketEvents();
    }

    registerSocketEvents() {
        // Username events
        this.socket.on('username_set', (data) => {
            this.username = data.username;
            this.showMessage(data.message, 'success');
            this.showScreen('lobby-menu-screen');
            document.getElementById('player-username').textContent = this.username;
        });

        this.socket.on('username_error', (data) => {
            this.showError('username-error', data.error);
        });

        // Lobby creation events
        this.socket.on('lobby_created', (data) => {
            this.currentLobby = data.lobby;
            this.isHost = true;
            this.showMessage(data.message, 'success');
            this.showLobbyRoom();
        });

        this.socket.on('lobby_joined', (data) => {
            this.currentLobby = data.lobby;
            this.isHost = false;
            this.username = data.assignedUsername; // Update if username was modified
            this.showMessage(data.message, 'success');
            this.showLobbyRoom();
        });

        this.socket.on('lobby_error', (data) => {
            this.showMessage(data.error, 'error');
            // Also show in relevant error containers
            if (document.getElementById('create-lobby-screen').classList.contains('active')) {
                this.showError('create-lobby-error', data.error);
            }
            if (document.getElementById('join-lobby-screen').classList.contains('active')) {
                this.showError('join-lobby-error', data.error);
            }
        });

        // Lobby room events
        this.socket.on('player_joined', (data) => {
            this.currentLobby = data.lobby;
            this.showMessage(data.message, 'success');
            this.updatePlayersDisplay();
            this.updateStartButton();
        });

        this.socket.on('player_left', (data) => {
            this.currentLobby = data.lobby;
            this.showMessage(data.message, 'warning');
            this.updatePlayersDisplay();
            this.updateStartButton();
        });

        this.socket.on('player_ready_changed', (data) => {
            this.currentLobby = data.lobby;
            this.showMessage(data.message, 'success');
            this.updatePlayersDisplay();
            this.updateStartButton();
        });

        this.socket.on('lobby_config_updated', (data) => {
            this.currentLobby = data.lobby;
            this.showMessage(data.message, 'success');
            this.updateSettingsDisplay();
        });

        this.socket.on('lobby_left', (data) => {
            this.currentLobby = null;
            this.isHost = false;
            this.isReady = false;
            this.showMessage(data.message, 'success');
            this.showScreen('lobby-menu-screen');
        });

        // Game transition events
        this.socket.on('transition_to_game', (data) => {
            console.log('Transitioning to game room:', data.gameId);
            // Store the secure token for game authentication
            localStorage.setItem('playerToken', data.playerToken);
            // Redirect to game room (clean URL)
            window.location.href = `/game/${data.gameId}`;
        });

        this.socket.on('game_error', (data) => {
            this.showMessage(data.error, 'error');
        });
    }

    // UI Management
    showScreen(screenId) {
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        
        // Show target screen
        document.getElementById(screenId).classList.add('active');
    }

    updateConnectionStatus(status, text) {
        const statusEl = document.getElementById('connection-status');
        const statusText = document.getElementById('status-text');
        
        statusEl.className = `connection-status ${status}`;
        statusText.textContent = text;
    }

    showMessage(message, type = 'info') {
        // Removed toast notifications
        console.log(`${type.toUpperCase()}: ${message}`);
    }

    showError(elementId, message) {
        const errorEl = document.getElementById(elementId);
        errorEl.textContent = message;
        errorEl.classList.add('show');
        
        // Hide after 5 seconds
        setTimeout(() => {
            errorEl.classList.remove('show');
        }, 5000);
    }

    hideError(elementId) {
        const errorEl = document.getElementById(elementId);
        errorEl.classList.remove('show');
    }

    // Event Binding
    bindEvents() {
        // Username screen
        document.getElementById('set-username-btn').addEventListener('click', () => {
            this.setUsername();
        });

        document.getElementById('username-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.setUsername();
            }
        });

        // Lobby menu
        document.getElementById('create-lobby-btn').addEventListener('click', () => {
            this.showScreen('create-lobby-screen');
        });

        document.getElementById('join-lobby-btn').addEventListener('click', () => {
            this.showScreen('join-lobby-screen');
        });

        // Create lobby screen
        document.getElementById('create-lobby-confirm-btn').addEventListener('click', () => {
            this.createLobby();
        });

        document.getElementById('create-lobby-cancel-btn').addEventListener('click', () => {
            this.showScreen('lobby-menu-screen');
        });

        // Join lobby screen
        document.getElementById('join-lobby-confirm-btn').addEventListener('click', () => {
            this.joinLobby();
        });

        document.getElementById('join-lobby-cancel-btn').addEventListener('click', () => {
            this.showScreen('lobby-menu-screen');
        });

        document.getElementById('lobby-code-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.joinLobby();
            }
        });

        // Auto-format lobby code input
        document.getElementById('lobby-code-input').addEventListener('input', (e) => {
            e.target.value = e.target.value.toUpperCase().replace(/[^A-Z]/g, '');
        });

        // Lobby room events
        document.getElementById('toggle-ready-btn').addEventListener('click', () => {
            this.toggleReady();
        });

        document.getElementById('leave-lobby-btn').addEventListener('click', () => {
            this.leaveLobby();
        });

        document.getElementById('copy-code-btn').addEventListener('click', () => {
            this.copyLobbyCode();
        });

        // Host-only settings
        document.getElementById('edit-settings-btn').addEventListener('click', () => {
            this.showSettingsEditor();
        });

        document.getElementById('save-settings-btn').addEventListener('click', () => {
            this.saveSettings();
        });

        document.getElementById('cancel-settings-btn').addEventListener('click', () => {
            this.hideSettingsEditor();
        });

        document.getElementById('start-game-btn').addEventListener('click', () => {
            this.startGame();
        });

        // Bind validation events
        this.bindValidationEvents();
    }

    bindValidationEvents() {
        // Auto-update big blind when small blind changes
        document.getElementById('small-blind-input').addEventListener('input', (e) => {
            const smallBlind = parseInt(e.target.value) || 1;
            const bigBlindInput = document.getElementById('big-blind-input');
            const currentBigBlind = parseInt(bigBlindInput.value) || 2;
            
            if (currentBigBlind <= smallBlind) {
                bigBlindInput.value = smallBlind * 2;
            }
        });

        // Ensure big blind is at least double small blind
        document.getElementById('big-blind-input').addEventListener('input', (e) => {
            const bigBlind = parseInt(e.target.value) || 2;
            const smallBlind = parseInt(document.getElementById('small-blind-input').value) || 1;
            
            if (bigBlind < smallBlind * 2) {
                e.target.value = smallBlind * 2;
            }
        });

        // Ensure starting funds is reasonable
        document.getElementById('starting-funds-input').addEventListener('input', (e) => {
            const funds = parseInt(e.target.value) || 100;
            const bigBlind = parseInt(document.getElementById('big-blind-input').value) || 10;
            
            if (funds < bigBlind * 10) {
                e.target.value = bigBlind * 10;
            }
        });
    }

    // Socket Actions
    setUsername() {
        const usernameInput = document.getElementById('username-input');
        const username = usernameInput.value.trim();
        
        this.hideError('username-error');
        
        if (!username) {
            this.showError('username-error', 'Username cannot be empty');
            return;
        }

        if (username.length < 2) {
            this.showError('username-error', 'Username must be at least 2 characters');
            return;
        }

        if (username.length > 20) {
            this.showError('username-error', 'Username must be less than 20 characters');
            return;
        }

        this.socket.emit('set_username', { username: username });
    }

    createLobby() {
        this.hideError('create-lobby-error');
        
        const lobbyName = document.getElementById('lobby-name-input').value.trim();
        const smallBlind = parseInt(document.getElementById('small-blind-input').value) || 5;
        const bigBlind = parseInt(document.getElementById('big-blind-input').value) || 10;
        const startingFunds = parseInt(document.getElementById('starting-funds-input').value) || 1000;
        const maxPlayers = parseInt(document.getElementById('max-players-input').value) || 8;

        // Validation
        if (bigBlind < smallBlind * 2) {
            this.showError('create-lobby-error', 'Big blind must be at least double the small blind');
            return;
        }

        if (startingFunds < bigBlind * 10) {
            this.showError('create-lobby-error', 'Starting funds must be at least 10 times the big blind');
            return;
        }

        this.socket.emit('create_lobby', {
            name: lobbyName || `${this.username}'s Table`,
            smallBlind: smallBlind,
            bigBlind: bigBlind,
            startingFunds: startingFunds,
            maxPlayers: maxPlayers
        });
    }

    joinLobby() {
        this.hideError('join-lobby-error');
        
        const lobbyCode = document.getElementById('lobby-code-input').value.trim().toUpperCase();
        
        if (!lobbyCode) {
            this.showError('join-lobby-error', 'Please enter a lobby code');
            return;
        }

        if (lobbyCode.length !== 6) {
            this.showError('join-lobby-error', 'Lobby code must be 6 letters');
            return;
        }

        if (!/^[A-Z]+$/.test(lobbyCode)) {
            this.showError('join-lobby-error', 'Lobby code must contain only letters');
            return;
        }

        this.socket.emit('join_lobby', { code: lobbyCode });
    }

    toggleReady() {
        this.socket.emit('toggle_ready');
    }

    leaveLobby() {
        if (confirm('Are you sure you want to leave the lobby?')) {
            this.socket.emit('leave_lobby');
        }
    }

    copyLobbyCode() {
        if (this.currentLobby) {
            navigator.clipboard.writeText(this.currentLobby.code).then(() => {
                this.showMessage('Lobby code copied to clipboard!', 'success');
            }).catch(() => {
                this.showMessage('Failed to copy lobby code', 'error');
            });
        }
    }

    startGame() {
        this.socket.emit('start_game');
    }

    // Settings Management
    showSettingsEditor() {
        const editor = document.getElementById('settings-editor');
        const display = document.getElementById('game-settings');
        
        // Populate current values
        document.getElementById('edit-small-blind').value = this.currentLobby.config.smallBlind;
        document.getElementById('edit-big-blind').value = this.currentLobby.config.bigBlind;
        document.getElementById('edit-starting-funds').value = this.currentLobby.config.startingFunds;
        
        display.style.display = 'none';
        editor.style.display = 'block';
    }

    hideSettingsEditor() {
        const editor = document.getElementById('settings-editor');
        const display = document.getElementById('game-settings');
        
        editor.style.display = 'none';
        display.style.display = 'block';
    }

    saveSettings() {
        const smallBlind = parseInt(document.getElementById('edit-small-blind').value) || 5;
        const bigBlind = parseInt(document.getElementById('edit-big-blind').value) || 10;
        const startingFunds = parseInt(document.getElementById('edit-starting-funds').value) || 1000;

        // Validation
        if (bigBlind < smallBlind * 2) {
            this.showMessage('Big blind must be at least double the small blind', 'error');
            return;
        }

        if (startingFunds < bigBlind * 10) {
            this.showMessage('Starting funds must be at least 10 times the big blind', 'error');
            return;
        }

        this.socket.emit('update_lobby_config', {
            smallBlind: smallBlind,
            bigBlind: bigBlind,
            startingFunds: startingFunds
        });

        this.hideSettingsEditor();
    }

    // Lobby Room Display Updates
    showLobbyRoom() {
        this.showScreen('lobby-room-screen');
        this.updateLobbyDisplay();
        this.updatePlayersDisplay();
        this.updateSettingsDisplay();
        this.updateHostControls();
        this.updateStartButton();
    }

    updateLobbyDisplay() {
        if (!this.currentLobby) return;
        
        document.getElementById('lobby-title').textContent = this.currentLobby.name;
        document.getElementById('lobby-code-text').textContent = this.currentLobby.code;
        document.getElementById('max-player-count').textContent = this.currentLobby.config.maxPlayers;
    }

    updatePlayersDisplay() {
        if (!this.currentLobby) return;
        
        const playersList = document.getElementById('players-list');
        const playerCount = document.getElementById('player-count');
        
        playerCount.textContent = this.currentLobby.players.length;
        
        playersList.innerHTML = '';
        
        this.currentLobby.players.forEach(player => {
            const playerEl = document.createElement('div');
            playerEl.className = 'player-item';
            
            if (player.isHost && player.isReady) {
                playerEl.classList.add('host', 'ready');
            } else if (player.isHost) {
                playerEl.classList.add('host');
            } else if (player.isReady) {
                playerEl.classList.add('ready');
            }
            
            // Update our ready status if this is us
            if (player.socketId === this.socket.id) {
                this.isReady = player.isReady;
                this.updateReadyButton();
            }
            
            const statusText = player.isHost ? (player.isReady ? 'HOST (READY)' : 'HOST (NOT READY)') : (player.isReady ? 'READY' : 'NOT READY');
            
            playerEl.innerHTML = `
                <span class="player-name">${player.username}</span>
                <span class="player-status">${statusText}</span>
            `;
            
            playersList.appendChild(playerEl);
        });
    }

    updateSettingsDisplay() {
        if (!this.currentLobby) return;
        
        document.getElementById('display-small-blind').textContent = this.currentLobby.config.smallBlind;
        document.getElementById('display-big-blind').textContent = this.currentLobby.config.bigBlind;
        document.getElementById('display-starting-funds').textContent = this.currentLobby.config.startingFunds;
    }

    updateHostControls() {
        const editButton = document.getElementById('edit-settings-btn');
        const startButton = document.getElementById('start-game-btn');
        
        if (this.isHost) {
            editButton.style.display = 'inline-block';
            startButton.style.display = 'inline-block';
        } else {
            editButton.style.display = 'none';
            startButton.style.display = 'none';
        }
    }

    updateReadyButton() {
        const readyButton = document.getElementById('toggle-ready-btn');
        
        if (this.isReady) {
            readyButton.textContent = 'Not Ready';
            readyButton.classList.remove('btn-secondary');
            readyButton.classList.add('btn-primary');
        } else {
            readyButton.textContent = 'Ready Up';
            readyButton.classList.remove('btn-primary');
            readyButton.classList.add('btn-secondary');
        }
    }

    updateStartButton() {
        if (!this.isHost || !this.currentLobby) return;
        
        const startButton = document.getElementById('start-game-btn');
        const players = this.currentLobby.players;
        
        // Need at least 2 players and all must be ready (including host)
        const canStart = players.length >= 2 && players.every(p => p.isReady);
        
        startButton.disabled = !canStart;
        
        if (canStart) {
            startButton.textContent = 'Start Game';
        } else if (players.length < 2) {
            startButton.textContent = 'Need More Players';
        } else {
            startButton.textContent = 'Waiting for Players';
        }
    }
}

// Initialize the client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.pokerClient = new PokerClient();
});