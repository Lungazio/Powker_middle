// ability-selection.js - Handle ability selection menus
class AbilitySelectionManager {
    constructor(gameClient) {
        this.gameClient = gameClient;
        this.currentAbility = null;
        this.currentChoices = null;
        this.selectionWindow = null;
        
        this.init();
    }

    init() {
        this.createSelectionWindow();
        this.bindEvents();
    }

    // Create the selection window overlay
    createSelectionWindow() {
        const overlay = document.createElement('div');
        overlay.id = 'ability-selection-overlay';
        overlay.className = 'ability-selection-overlay hidden';
        
        overlay.innerHTML = `
            <div class="ability-selection-window">
                <div class="ability-selection-header">
                    <h3 id="ability-selection-title">Choose Action</h3>
                    <button id="ability-selection-close" class="ability-close-btn">&times;</button>
                </div>
                <div class="ability-selection-body">
                    <p id="ability-selection-message">Select an option:</p>
                    <div id="ability-selection-content"></div>
                </div>
                <div class="ability-selection-footer">
                    <button id="ability-cancel-btn" class="btn btn-secondary">Cancel</button>
                    <button id="ability-confirm-btn" class="btn btn-primary">Confirm</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        this.selectionWindow = overlay;
    }

    bindEvents() {
        // Close button
        document.getElementById('ability-selection-close').addEventListener('click', () => {
            this.hideSelectionWindow();
        });
        
        // Cancel button
        document.getElementById('ability-cancel-btn').addEventListener('click', () => {
            this.cancelAbility();
        });
        
        // Confirm button
        document.getElementById('ability-confirm-btn').addEventListener('click', () => {
            this.confirmSelection();
        });

        // Click outside to close
        this.selectionWindow.addEventListener('click', (e) => {
            if (e.target === this.selectionWindow) {
                this.hideSelectionWindow();
            }
        });
    }

    // Main method called when Flask sends ability_choice_required
    showAbilitySelection(data) {
        this.currentAbility = data.abilityUsed;
        this.currentChoices = data;
        
        const title = this.getAbilityTitle(data);
        const message = data.message || data.instructions || 'Make your selection';
        
        document.getElementById('ability-selection-title').textContent = title;
        document.getElementById('ability-selection-message').textContent = message;
        
        // Clear previous content
        const content = document.getElementById('ability-selection-content');
        content.innerHTML = '';
        
        // Create appropriate UI based on ability type
        switch (data.abilityUsed.toLowerCase()) {
            case 'peek':
                this.createPeekInterface(content, data);
                break;
            case 'burn':
                this.createBurnInterface(content, data);
                break;
            case 'manifest':
                this.createManifestInterface(content, data);
                break;
            case 'trashman':
                this.createTrashmanInterface(content, data);
                break;
            case 'yoink':
                this.createYoinkInterface(content, data);
                break;
            default:
                this.createGenericInterface(content, data);
        }
        
        this.selectionWindow.classList.remove('hidden');
        this.gameClient.addActionLog(`${title} - ${message}`, 'system');
    }

    // Peek: Player selection + card choice
    createPeekInterface(container, data) {
        const players = data.availablePlayers || [];
        const cardOptions = data.cardOptions || [
            {index: 0, name: 'First Card'},
            {index: 1, name: 'Second Card'}
        ];

        container.innerHTML = `
            <div class="selection-group">
                <label for="peek-player">Target Player:</label>
                <select id="peek-player" class="selection-input">
                    <option value="">Choose player...</option>
                    ${players.map(p => 
                        `<option value="${p.id}">${p.name} ($${p.balance})</option>`
                    ).join('')}
                </select>
            </div>
            <div class="selection-group">
                <label for="peek-card">Card to Peek:</label>
                <select id="peek-card" class="selection-input">
                    <option value="">Choose card...</option>
                    ${cardOptions.map(c => 
                        `<option value="${c.index}">${c.name}</option>`
                    ).join('')}
                </select>
            </div>
        `;
    }

    // Burn: Suit vs Rank choice
    createBurnInterface(container, data) {
        const options = data.revealOptions || [
            {value: true, name: 'Reveal Suit'},
            {value: false, name: 'Reveal Rank'}
        ];

        container.innerHTML = `
            <div class="selection-group">
                <label>What to reveal:</label>
                <div class="radio-group">
                    ${options.map((option, index) => `
                        <label class="radio-option">
                            <input type="radio" name="burn-choice" value="${option.value}" ${index === 0 ? 'checked' : ''}>
                            <span>${option.name}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Manifest: Card selection grid
    createManifestInterface(container, data) {
        const cards = data.availableCards || [];
        const drawnCard = data.drawnCard;

        container.innerHTML = `
            <div class="selection-group">
                <label>Choose card to discard:</label>
                ${drawnCard ? `<p class="drawn-card-info">New card drawn: <strong>${drawnCard.Card || 'Unknown'}</strong></p>` : ''}
                <div class="card-selection-grid">
                    ${cards.map(card => `
                        <button class="card-selection-btn" data-index="${card.index}" data-card="${card.card}">
                            <div class="card-name">${card.card}</div>
                            <div class="card-type">${card.isDrawnCard ? '(New)' : '(Current)'}</div>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;

        // Bind card selection
        this.bindCardSelection();
    }

    // Trashman: Multi-step interface
    createTrashmanInterface(container, data) {
        const step = data.step || 1;

        if (step === 1) {
            // Step 1: Choose burnt card
            const burntCards = data.availableBurntCards || [];
            const currentHole = data.currentHoleCards || [];

            container.innerHTML = `
                <div class="selection-group">
                    <label>Current hole cards: <strong>${currentHole.join(', ')}</strong></label>
                    <label>Choose burnt card to retrieve:</label>
                    <div class="card-selection-grid">
                        ${burntCards.map(card => `
                            <button class="card-selection-btn" data-index="${card.index}" data-card="${card.card}">
                                <div class="card-name">${card.card}</div>
                                <div class="card-type">(Burnt)</div>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        } else {
            // Step 2: Choose hole card to discard
            const holeCards = data.availableHoleCards || [];
            const chosenBurnt = data.chosenBurntCard;

            container.innerHTML = `
                <div class="selection-group">
                    <label>Retrieving: <strong>${chosenBurnt ? chosenBurnt.card : 'Unknown'}</strong></label>
                    <label>Choose hole card to discard:</label>
                    <div class="card-selection-grid">
                        ${holeCards.map(card => `
                            <button class="card-selection-btn" data-index="${card.index}" data-card="${card.card}">
                                <div class="card-name">${card.card}</div>
                                <div class="card-type">(Current)</div>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        this.bindCardSelection();
    }

    // Yoink: Two card grids (hole + board)
    createYoinkInterface(container, data) {
        const holeCards = data.availableHoleCards || [];
        const boardCards = data.availableBoardCards || [];

        container.innerHTML = `
            <div class="selection-group">
                <label>Your hole cards (choose one):</label>
                <div class="card-selection-grid" id="yoink-hole-grid">
                    ${holeCards.map(card => `
                        <button class="card-selection-btn hole-card" data-index="${card.index}" data-card="${card.card}">
                            <div class="card-name">${card.card}</div>
                            <div class="card-type">(Your card)</div>
                        </button>
                    `).join('')}
                </div>
            </div>
            <div class="selection-group">
                <label>Board cards (choose one):</label>
                <div class="card-selection-grid" id="yoink-board-grid">
                    ${boardCards.map(card => `
                        <button class="card-selection-btn board-card" data-index="${card.index}" data-card="${card.card}">
                            <div class="card-name">${card.card}</div>
                            <div class="card-type">(Board card)</div>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;

        this.bindCardSelection();
    }

    // Generic interface for unknown abilities
    createGenericInterface(container, data) {
        container.innerHTML = `
            <div class="selection-group">
                <p>Ability data received but no specific interface available.</p>
                <pre>${JSON.stringify(data, null, 2)}</pre>
            </div>
        `;
    }

    // Bind card selection events
    bindCardSelection() {
        document.querySelectorAll('.card-selection-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const grid = e.target.closest('.card-selection-grid');
                
                // For Yoink, allow one selection in each grid
                if (grid.id === 'yoink-hole-grid' || grid.id === 'yoink-board-grid') {
                    grid.querySelectorAll('.card-selection-btn').forEach(b => 
                        b.classList.remove('selected'));
                } else {
                    // For other abilities, only one selection total
                    document.querySelectorAll('.card-selection-btn').forEach(b => 
                        b.classList.remove('selected'));
                }
                
                e.target.closest('.card-selection-btn').classList.add('selected');
            });
        });
    }

    // Get display title for ability
    getAbilityTitle(data) {
        const ability = data.abilityUsed.toLowerCase();
        const step = data.step;
        
        const titles = {
            'peek': 'Peek Ability',
            'burn': 'Burn Ability',
            'manifest': 'Manifest Ability',
            'trashman': `Trashman Ability${step ? ` - Step ${step}` : ''}`,
            'deadman': 'Deadman Ability',
            'chaos': 'Chaos Ability',
            'yoink': 'Yoink Ability'
        };
        
        return titles[ability] || `${ability} Ability`;
    }

    // Confirm current selection
    confirmSelection() {
        if (!this.currentAbility || !this.currentChoices) {
            return;
        }

        const selection = this.getSelectionData();
        if (!selection) {
            this.gameClient.addActionLog('Please make a selection before confirming', 'system');
            return;
        }

        // Send selection back to Flask
        this.gameClient.socket.emit('use_ability', {
            gameId: this.gameClient.gameId,
            ability: this.currentAbility,
            ...selection
        });

        this.hideSelectionWindow();
        this.gameClient.addActionLog(`${this.getAbilityTitle(this.currentChoices)} - Selection confirmed`, 'player-action');
    }

    // Extract selection data based on current ability
    getSelectionData() {
        switch (this.currentAbility.toLowerCase()) {
            case 'peek':
                return this.getPeekSelection();
            case 'burn':
                return this.getBurnSelection();
            case 'manifest':
                return this.getManifestSelection();
            case 'trashman':
                return this.getTrashmanSelection();
            case 'yoink':
                return this.getYoinkSelection();
            default:
                return null;
        }
    }

    getPeekSelection() {
        const playerId = document.getElementById('peek-player')?.value;
        const cardIndex = document.getElementById('peek-card')?.value;
        
        if (!playerId || cardIndex === '') {
            return null;
        }
        
        return {
            targetPlayerId: parseInt(playerId),
            cardIndex: parseInt(cardIndex)
        };
    }

    getBurnSelection() {
        const selected = document.querySelector('input[name="burn-choice"]:checked');
        if (!selected) return null;
        
        return {
            revealSuit: selected.value === 'true'
        };
    }

    getManifestSelection() {
        const selected = document.querySelector('.card-selection-btn.selected');
        if (!selected) return null;
        
        const drawnCard = this.currentChoices.drawnCard;
        
        return {
            discardIndex: parseInt(selected.dataset.index),
            drawnCard: drawnCard ? drawnCard.Rank : null,
            drawnCardSuit: drawnCard ? drawnCard.Suit : null
        };
    }

    getTrashmanSelection() {
        const selected = document.querySelector('.card-selection-btn.selected');
        if (!selected) return null;
        
        const step = this.currentChoices.step || 1;
        
        if (step === 1) {
            return {
                burntCardIndex: parseInt(selected.dataset.index)
            };
        } else {
            return {
                burntCardIndex: this.currentChoices.chosenBurntCard?.index || 0,
                holeCardIndex: parseInt(selected.dataset.index)
            };
        }
    }

    getYoinkSelection() {
        const holeSelected = document.querySelector('#yoink-hole-grid .card-selection-btn.selected');
        const boardSelected = document.querySelector('#yoink-board-grid .card-selection-btn.selected');
        
        if (!holeSelected || !boardSelected) return null;
        
        return {
            cardIndex: parseInt(holeSelected.dataset.index),      // hole card index
            targetPlayerId: parseInt(boardSelected.dataset.index) // board card index (API naming)
        };
    }

    // Cancel ability
    cancelAbility() {
        this.gameClient.socket.emit('cancel_ability', {
            gameId: this.gameClient.gameId
        });
        
        this.hideSelectionWindow();
        this.gameClient.addActionLog('Ability cancelled', 'system');
    }

    // Hide selection window
    hideSelectionWindow() {
        this.selectionWindow.classList.add('hidden');
        this.currentAbility = null;
        this.currentChoices = null;
    }

    // Method called by game client when choice is required
    handleAbilityChoiceRequired(data) {
        console.log('Ability choice required:', data);
        this.showAbilitySelection(data);
    }
}

// Export for use in game.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AbilitySelectionManager;
}