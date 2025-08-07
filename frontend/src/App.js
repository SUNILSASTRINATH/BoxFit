import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

const TETRIS_PIECES = {
  I: { shape: [[1, 1, 1, 1]], color: "#00FFFF" },
  O: { shape: [[1, 1], [1, 1]], color: "#FFFF00" },
  T: { shape: [[0, 1, 0], [1, 1, 1]], color: "#800080" },
  L: { shape: [[1, 0, 0], [1, 1, 1]], color: "#FFA500" },
  J: { shape: [[0, 0, 1], [1, 1, 1]], color: "#0000FF" },
  S: { shape: [[0, 1, 1], [1, 1, 0]], color: "#00FF00" },
  Z: { shape: [[1, 1, 0], [0, 1, 1]], color: "#FF0000" }
};

function App() {
  const [gameState, setGameState] = useState({
    grid: Array(10).fill().map(() => Array(10).fill(null)),
    players: {},
    score: 0,
    nextPiece: null,
    playerName: '',
    playerColor: ''
  });
  
  const [roomId, setRoomId] = useState('');
  const [playerName, setPlayerName] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [currentPiece, setCurrentPiece] = useState(null);
  const [dragState, setDragState] = useState({ isDragging: false, startX: 0, startY: 0 });
  const [piecePosition, setPiecePosition] = useState({ x: 0, y: 0 });
  const [isValidPlacement, setIsValidPlacement] = useState(true);
  
  const wsRef = useRef(null);
  const gridRef = useRef(null);

  const connectToGame = useCallback(() => {
    if (!roomId || !playerName || wsRef.current) return;

    const wsUrl = `${WS_URL}/api/ws/${roomId}/${playerName}`;
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setIsConnected(true);
      console.log('Connected to game');
    };

    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'game_state':
          setGameState(message.data);
          break;
        case 'player_joined':
        case 'player_left':
          setGameState(prev => ({ ...prev, players: message.data.players }));
          break;
        case 'piece_placed':
          setGameState(prev => ({
            ...prev,
            grid: message.data.grid,
            score: message.data.score,
            nextPiece: message.data.next_piece
          }));
          setCurrentPiece(null);
          break;
        case 'piece_rotated':
          if (currentPiece) {
            setCurrentPiece(prev => ({ ...prev, shape: message.data.shape }));
          }
          break;
        default:
          break;
      }
    };

    wsRef.current.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }, [roomId, playerName, WS_URL]);

  const joinGame = () => {
    if (roomId && playerName) {
      connectToGame();
    }
  };

  const getNewPiece = () => {
    if (gameState.nextPiece) {
      setCurrentPiece({
        ...gameState.nextPiece,
        id: Date.now()
      });
    }
  };

  const rotatePiece = () => {
    if (currentPiece && wsRef.current) {
      wsRef.current.send(JSON.stringify({
        type: 'rotate_piece',
        data: { shape: currentPiece.shape }
      }));
    }
  };

  const checkValidPlacement = useCallback((shape, x, y) => {
    for (let row = 0; row < shape.length; row++) {
      for (let col = 0; col < shape[row].length; col++) {
        if (shape[row][col] === 1) {
          const gridX = Math.floor(x / 40) + col;
          const gridY = Math.floor(y / 40) + row;
          
          if (gridX < 0 || gridX >= 10 || gridY < 0 || gridY >= 10) {
            return false;
          }
          
          if (gameState.grid[gridY] && gameState.grid[gridY][gridX] !== null) {
            return false;
          }
        }
      }
    }
    return true;
  }, [gameState.grid]);

  const handleMouseDown = (e) => {
    if (!currentPiece) return;
    
    e.preventDefault();
    setDragState({
      isDragging: true,
      startX: e.clientX,
      startY: e.clientY
    });
    
    // Start with the current piece position
    if (gridRef.current) {
      const rect = gridRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - 20; // Center the piece on cursor
      const y = e.clientY - rect.top - 20;
      setPiecePosition({ x: Math.max(0, x), y: Math.max(0, y) });
    }
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragState.isDragging || !currentPiece || !gridRef.current) return;
    
    e.preventDefault();
    const rect = gridRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - 20; // Offset to center piece on cursor
    const y = e.clientY - rect.top - 20;
    
    const clampedX = Math.max(0, Math.min(x, 360)); // Keep within grid bounds
    const clampedY = Math.max(0, Math.min(y, 360));
    
    setPiecePosition({ x: clampedX, y: clampedY });
    
    const isValid = checkValidPlacement(currentPiece.shape, clampedX, clampedY);
    setIsValidPlacement(isValid);
  }, [dragState.isDragging, currentPiece, checkValidPlacement]);

  const handleMouseUp = useCallback((e) => {
    if (!dragState.isDragging || !currentPiece) return;
    
    e.preventDefault();
    setDragState({ isDragging: false, startX: 0, startY: 0 });
    
    if (gridRef.current) {
      const rect = gridRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const gridX = Math.floor(x / 40);
      const gridY = Math.floor(y / 40);
      
      if (checkValidPlacement(currentPiece.shape, x, y) && wsRef.current) {
        console.log('Placing piece at:', { gridX, gridY });
        wsRef.current.send(JSON.stringify({
          type: 'place_piece',
          data: {
            shape: currentPiece.shape,
            position: { x: gridX, y: gridY },
            color: currentPiece.color
          }
        }));
      } else {
        console.log('Invalid placement attempted');
      }
    }
    
    setPiecePosition({ x: 0, y: 0 });
    setIsValidPlacement(true);
  }, [dragState.isDragging, currentPiece, checkValidPlacement]);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  const renderGrid = () => {
    const grid = [];
    for (let row = 0; row < 10; row++) {
      for (let col = 0; col < 10; col++) {
        const cell = gameState.grid[row][col];
        grid.push(
          <div
            key={`${row}-${col}`}
            className="grid-cell"
            style={{
              backgroundColor: cell ? cell.color : 'transparent',
              borderColor: cell ? '#444' : '#333'
            }}
          />
        );
      }
    }
    return grid;
  };

  const renderPiece = (piece, position = { x: 0, y: 0 }, className = '', isNextPiece = false) => {
    if (!piece) return null;
    
    const cells = [];
    
    // For next piece display, center it in the container
    let offsetX = position.x;
    let offsetY = position.y;
    
    if (isNextPiece) {
      const shapeWidth = piece.shape[0] ? piece.shape[0].length : 0;
      const shapeHeight = piece.shape.length;
      offsetX = (120 - shapeWidth * 30) / 2; // Center horizontally in 120px container
      offsetY = (120 - shapeHeight * 30) / 2; // Center vertically in 120px container
    }
    
    piece.shape.forEach((row, rowIndex) => {
      row.forEach((cell, colIndex) => {
        if (cell === 1) {
          cells.push(
            <div
              key={`${rowIndex}-${colIndex}`}
              className={`piece-cell ${className}`}
              style={{
                left: offsetX + colIndex * (isNextPiece ? 30 : 40),
                top: offsetY + rowIndex * (isNextPiece ? 30 : 40),
                width: isNextPiece ? '30px' : '40px',
                height: isNextPiece ? '30px' : '40px',
                backgroundColor: piece.color,
                opacity: className === 'dragging' ? (isValidPlacement ? 0.8 : 0.4) : 1,
                borderColor: className === 'dragging' ? (isValidPlacement ? piece.color : '#ff4444') : piece.color
              }}
            />
          );
        }
      });
    });
    return cells;
  };

  if (!isConnected) {
    return (
      <div className="join-screen">
        <div className="join-form">
          <h1>BoxFit</h1>
          <p>Collaborative Packing Game</p>
          <div className="form-group">
            <input
              type="text"
              placeholder="Room ID"
              value={roomId}
              onChange={(e) => setRoomId(e.target.value)}
            />
          </div>
          <div className="form-group">
            <input
              type="text"
              placeholder="Your Name"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
            />
          </div>
          <button onClick={joinGame} disabled={!roomId || !playerName}>
            Join Game
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="game-container">
      <div className="game-header">
        <h1>BoxFit</h1>
        <div className="room-info">
          Room: {roomId} | Player: {playerName}
        </div>
      </div>
      
      <div className="game-content">
        <div className="game-grid-container">
          <div
            ref={gridRef}
            className="game-grid"
            onMouseDown={handleMouseDown}
          >
            {renderGrid()}
            {dragState.isDragging && currentPiece && renderPiece(currentPiece, piecePosition, 'dragging')}
          </div>
          <div className="score">Score: {gameState.score}</div>
        </div>
        
        <div className="game-sidebar">
          <div className="next-piece-section">
            <h3>Next Item</h3>
            <div className="next-piece-container">
              {gameState.nextPiece && renderPiece(gameState.nextPiece, { x: 0, y: 0 }, '', true)}
            </div>
            <button 
              onClick={getNewPiece}
              disabled={!!currentPiece}
              className="get-piece-btn"
            >
              Get Piece
            </button>
            {currentPiece && (
              <div className="current-piece-display">
                <p>Current Piece: {currentPiece.type}</p>
                <button onClick={rotatePiece} className="rotate-btn">
                  Rotate
                </button>
              </div>
            )}
          </div>
          
          <div className="players-section">
            <h3>Players</h3>
            <div className="players-list">
              {Object.entries(gameState.players).map(([name, data]) => (
                <div key={name} className="player-item">
                  <div 
                    className="player-color" 
                    style={{ backgroundColor: data.color }}
                  />
                  <span className={`player-name ${!data.connected ? 'disconnected' : ''}`}>
                    {name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;