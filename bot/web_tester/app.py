"""
Web Mic Tester for AI Voice Bot
FastAPI + WebSocket for live testing with browser microphone
"""

import logging
import uuid
import json
from typing import Dict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Import bot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_engine import create_session, ConversationState, StateEngine
from stt import transcribe_audio
from tts import get_tts_engine
from config import AUDIO_CACHE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CollectOS Bot Web Tester")

# Active sessions
active_sessions: Dict[str, tuple] = {}


@app.get("/")
async def get_index():
    """Serve web tester interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CollectOS Bot Tester</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .status {
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                text-align: center;
            }
            .status.disconnected { background-color: #ffebee; color: #c62828; }
            .status.connected { background-color: #e8f5e9; color: #2e7d32; }
            .status.recording { background-color: #fff3e0; color: #ef6c00; }
            button {
                padding: 12px 24px;
                margin: 5px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .start-btn {
                background-color: #4caf50;
                color: white;
            }
            .stop-btn {
                background-color: #f44336;
                color: white;
            }
            .record-btn {
                background-color: #2196f3;
                color: white;
            }
            .conversation {
                margin-top: 20px;
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
            }
            .message {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .message.bot {
                background-color: #e3f2fd;
                margin-right: 50px;
            }
            .message.user {
                background-color: #f3e5f5;
                margin-left: 50px;
            }
            .message .speaker {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .controls {
                text-align: center;
                margin: 20px 0;
            }
            .info {
                background-color: #fff9c4;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 CollectOS Voice Bot Tester</h1>

            <div class="info">
                <strong>Instructions:</strong><br>
                1. Click "Start Session" to begin<br>
                2. The bot will greet you<br>
                3. Click "Record Response" and speak into your microphone<br>
                4. The bot will respond based on your input<br>
                <br>
                <strong>Note:</strong> This is a simplified demo. Full audio streaming requires additional setup.
            </div>

            <div id="status" class="status disconnected">
                Disconnected
            </div>

            <div class="controls">
                <button id="startBtn" class="start-btn" onclick="startSession()">
                    Start Session
                </button>
                <button id="recordBtn" class="record-btn" onclick="recordResponse()" disabled>
                    Record Response
                </button>
                <button id="endBtn" class="stop-btn" onclick="endSession()" disabled>
                    End Session
                </button>
            </div>

            <div id="conversation" class="conversation">
                <p style="text-align: center; color: #999;">
                    Conversation will appear here...
                </p>
            </div>
        </div>

        <script>
            let ws = null;
            let sessionId = null;

            function updateStatus(text, className) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.className = 'status ' + className;
            }

            function addMessage(speaker, text) {
                const conversation = document.getElementById('conversation');
                if (conversation.children[0]?.textContent.includes('Conversation will appear')) {
                    conversation.innerHTML = '';
                }

                const messageDiv = document.createElement('div');
                messageDiv.className = 'message ' + speaker.toLowerCase();
                messageDiv.innerHTML = `
                    <div class="speaker">${speaker}:</div>
                    <div>${text}</div>
                `;
                conversation.appendChild(messageDiv);
                conversation.scrollTop = conversation.scrollHeight;
            }

            function enableControls(start, record, end) {
                document.getElementById('startBtn').disabled = !start;
                document.getElementById('recordBtn').disabled = !record;
                document.getElementById('endBtn').disabled = !end;
            }

            function startSession() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;

                ws = new WebSocket(wsUrl);

                ws.onopen = () => {
                    updateStatus('Connected - Starting session...', 'connected');
                    ws.send(JSON.stringify({
                        action: 'start',
                        account_id: 'ACC001',
                        flow_type: 'post_bounce_ptp'
                    }));
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);

                    if (data.type === 'session_started') {
                        sessionId = data.session_id;
                        updateStatus('Session Active - Bot is speaking...', 'connected');
                        enableControls(false, true, true);
                        addMessage('Bot', data.message);
                    } else if (data.type === 'bot_response') {
                        addMessage('Bot', data.message);
                        if (data.continue) {
                            enableControls(false, true, true);
                        } else {
                            updateStatus('Session Ended', 'disconnected');
                            enableControls(true, false, false);
                        }
                    } else if (data.type === 'error') {
                        updateStatus('Error: ' + data.message, 'disconnected');
                        enableControls(true, false, false);
                    }
                };

                ws.onerror = (error) => {
                    updateStatus('WebSocket Error', 'disconnected');
                    enableControls(true, false, false);
                };

                ws.onclose = () => {
                    updateStatus('Disconnected', 'disconnected');
                    enableControls(true, false, false);
                };
            }

            function recordResponse() {
                // Simplified: Use prompt for text input
                // In full version, this would record audio from microphone
                const userInput = prompt('Enter your response (simulated speech):');

                if (userInput && userInput.trim()) {
                    addMessage('User', userInput);
                    updateStatus('Processing...', 'recording');
                    enableControls(false, false, true);

                    ws.send(JSON.stringify({
                        action: 'user_input',
                        session_id: sessionId,
                        text: userInput,
                        confidence: 0.9
                    }));
                }
            }

            function endSession() {
                if (ws) {
                    ws.send(JSON.stringify({
                        action: 'end',
                        session_id: sessionId
                    }));
                    ws.close();
                }
                updateStatus('Disconnected', 'disconnected');
                enableControls(true, false, false);
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for bot communication."""
    await websocket.accept()
    session_id = None
    state = None
    engine = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "start":
                # Create new session
                session_id = str(uuid.uuid4())
                account_id = message.get("account_id", "ACC001")
                flow_type = message.get("flow_type", "post_bounce_ptp")

                state, engine = create_session(session_id, account_id, flow_type)

                # Get initial bot response
                initial_response = engine.get_initial_response({
                    "customer_name": "Customer",
                    "product_type": "Auto Loan",
                })

                state.add_turn("bot", initial_response)

                await websocket.send_text(json.dumps({
                    "type": "session_started",
                    "session_id": session_id,
                    "message": initial_response,
                }))

            elif action == "user_input":
                if not state or not engine:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "No active session"
                    }))
                    continue

                user_text = message.get("text", "")
                confidence = message.get("confidence", 0.9)

                # Process turn
                bot_response, should_continue = engine.process_turn(
                    state, user_text, confidence
                )

                await websocket.send_text(json.dumps({
                    "type": "bot_response",
                    "message": bot_response,
                    "continue": should_continue,
                    "disposition": state.disposition,
                }))

            elif action == "end":
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bot_web_tester"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
