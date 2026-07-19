"""
Enhanced Web Mic Tester with ACTUAL Audio Support
Record from browser microphone, transcribe with STT, talk to bot live
"""

import logging
import uuid
import json
import base64
import io
import wave
from typing import Dict
from pathlib import Path
import tempfile

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Import bot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_engine import create_session, ConversationState, StateEngine
from stt import transcribe_audio
from config import AUDIO_CACHE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CollectOS Bot Audio Tester")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active sessions
active_sessions: Dict[str, tuple] = {}


@app.get("/")
async def get_index():
    """Serve enhanced web tester with audio support."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CollectOS Bot Audio Tester</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 50px auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 10px;
            }
            .subtitle {
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .status {
                padding: 15px;
                margin: 15px 0;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            .status.disconnected { background-color: #ffebee; color: #c62828; }
            .status.connected { background-color: #e8f5e9; color: #2e7d32; }
            .status.recording { background-color: #fff3e0; color: #ef6c00; animation: pulse 1.5s infinite; }
            .status.processing { background-color: #e3f2fd; color: #1565c0; }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.7; }
            }

            button {
                padding: 15px 30px;
                margin: 8px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            button:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .start-btn {
                background: linear-gradient(135deg, #4caf50, #45a049);
                color: white;
            }
            .stop-btn {
                background: linear-gradient(135deg, #f44336, #d32f2f);
                color: white;
            }
            .record-btn {
                background: linear-gradient(135deg, #2196f3, #1976d2);
                color: white;
            }
            .record-btn.recording {
                background: linear-gradient(135deg, #ff5722, #e64a19);
                animation: pulse 1.5s infinite;
            }
            .conversation {
                margin-top: 25px;
                max-height: 450px;
                overflow-y: auto;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                padding: 20px;
                background-color: #fafafa;
            }
            .message {
                margin: 12px 0;
                padding: 12px 18px;
                border-radius: 10px;
                animation: slideIn 0.3s ease;
            }
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .message.bot {
                background: linear-gradient(135deg, #e3f2fd, #bbdefb);
                margin-right: 80px;
                border-left: 4px solid #2196f3;
            }
            .message.user {
                background: linear-gradient(135deg, #f3e5f5, #e1bee7);
                margin-left: 80px;
                border-right: 4px solid #9c27b0;
            }
            .message .speaker {
                font-weight: bold;
                margin-bottom: 6px;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .message.bot .speaker { color: #1565c0; }
            .message.user .speaker { color: #7b1fa2; }
            .message .text {
                line-height: 1.5;
            }
            .controls {
                text-align: center;
                margin: 25px 0;
            }
            .info {
                background: linear-gradient(135deg, #fff9c4, #fff59d);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                border-left: 5px solid #f57f17;
            }
            .info strong {
                color: #f57f17;
            }
            .audio-visualizer {
                height: 60px;
                background-color: #f5f5f5;
                border-radius: 8px;
                margin: 15px 0;
                display: none;
                align-items: center;
                justify-content: center;
                border: 2px solid #e0e0e0;
            }
            .audio-visualizer.active {
                display: flex;
            }
            .visualizer-bar {
                width: 4px;
                height: 20px;
                background-color: #2196f3;
                margin: 0 2px;
                border-radius: 2px;
                animation: visualize 0.6s ease-in-out infinite;
            }
            .visualizer-bar:nth-child(2) { animation-delay: 0.1s; }
            .visualizer-bar:nth-child(3) { animation-delay: 0.2s; }
            .visualizer-bar:nth-child(4) { animation-delay: 0.3s; }
            .visualizer-bar:nth-child(5) { animation-delay: 0.4s; }

            @keyframes visualize {
                0%, 100% { height: 20px; }
                50% { height: 45px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 CollectOS Voice Bot - Live Audio Tester</h1>
            <div class="subtitle">Talk to the bot using your microphone!</div>

            <div class="info">
                <strong>🎤 How to Use:</strong><br>
                1. Click "Start Session" to begin<br>
                2. Grant microphone permission when prompted<br>
                3. Bot will speak - you'll see the text response<br>
                4. Click "Record Your Response" and speak<br>
                5. Your speech will be transcribed and bot will respond<br>
                <br>
                <strong>⚠️ Note:</strong> Make sure your microphone is working and browser has permission.
            </div>

            <div id="status" class="status disconnected">
                Disconnected - Click "Start Session" to begin
            </div>

            <div id="audioVisualizer" class="audio-visualizer">
                <div class="visualizer-bar"></div>
                <div class="visualizer-bar"></div>
                <div class="visualizer-bar"></div>
                <div class="visualizer-bar"></div>
                <div class="visualizer-bar"></div>
            </div>

            <div class="controls">
                <button id="startBtn" class="start-btn" onclick="startSession()">
                    🚀 Start Session
                </button>
                <button id="recordBtn" class="record-btn" onclick="toggleRecording()" disabled>
                    🎤 Record Your Response
                </button>
                <button id="endBtn" class="stop-btn" onclick="endSession()" disabled>
                    ⏹️ End Session
                </button>
            </div>

            <div id="conversation" class="conversation">
                <p style="text-align: center; color: #999; font-style: italic;">
                    💬 Conversation will appear here...
                </p>
            </div>
        </div>

        <script>
            let ws = null;
            let sessionId = null;
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;
            let stream = null;

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
                    <div class="speaker">${speaker}</div>
                    <div class="text">${text}</div>
                `;
                conversation.appendChild(messageDiv);
                conversation.scrollTop = conversation.scrollHeight;
            }

            function enableControls(start, record, end) {
                document.getElementById('startBtn').disabled = !start;
                document.getElementById('recordBtn').disabled = !record;
                document.getElementById('endBtn').disabled = !end;
            }

            function showVisualizer(show) {
                const visualizer = document.getElementById('audioVisualizer');
                visualizer.className = 'audio-visualizer' + (show ? ' active' : '');
            }

            async function startSession() {
                // Request microphone permission
                try {
                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    console.log('Microphone access granted');
                } catch (err) {
                    alert('Microphone access denied! Please grant permission and try again.');
                    return;
                }

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
                        updateStatus('✅ Session Active - Listen to bot, then record your response', 'connected');
                        enableControls(false, true, true);
                        addMessage('Bot', data.message);

                        // Speak the bot's message using browser TTS
                        speakText(data.message);
                    } else if (data.type === 'bot_response') {
                        addMessage('Bot', data.message);
                        speakText(data.message);

                        if (data.continue) {
                            updateStatus('✅ Listening - Record your response', 'connected');
                            enableControls(false, true, true);
                        } else {
                            updateStatus('Session Ended - Disposition: ' + (data.disposition || 'N/A'), 'disconnected');
                            enableControls(true, false, false);
                            if (stream) {
                                stream.getTracks().forEach(track => track.stop());
                            }
                        }
                    } else if (data.type === 'transcription') {
                        addMessage('User (transcribed)', data.text);
                        updateStatus('🤖 Bot is thinking...', 'processing');
                    } else if (data.type === 'error') {
                        updateStatus('❌ Error: ' + data.message, 'disconnected');
                        enableControls(true, false, false);
                    }
                };

                ws.onerror = (error) => {
                    updateStatus('❌ WebSocket Error', 'disconnected');
                    enableControls(true, false, false);
                };

                ws.onclose = () => {
                    updateStatus('Disconnected', 'disconnected');
                    enableControls(true, false, false);
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }
                };
            }

            function speakText(text) {
                // Use browser's built-in text-to-speech
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 0.9;
                utterance.pitch = 1.0;
                utterance.volume = 1.0;
                window.speechSynthesis.speak(utterance);
            }

            async function toggleRecording() {
                if (isRecording) {
                    stopRecording();
                } else {
                    startRecording();
                }
            }

            function startRecording() {
                if (!stream) {
                    alert('Microphone not initialized');
                    return;
                }

                audioChunks = [];
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

                    // Convert to base64
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        const base64Audio = reader.result.split(',')[1];

                        // Send to server for transcription
                        ws.send(JSON.stringify({
                            action: 'audio_input',
                            session_id: sessionId,
                            audio_data: base64Audio,
                            format: 'webm'
                        }));
                    };
                };

                mediaRecorder.start();
                isRecording = true;

                const recordBtn = document.getElementById('recordBtn');
                recordBtn.textContent = '⏹️ Stop Recording';
                recordBtn.className = 'record-btn recording';

                updateStatus('🎤 Recording... Speak now!', 'recording');
                showVisualizer(true);
            }

            function stopRecording() {
                if (mediaRecorder && isRecording) {
                    mediaRecorder.stop();
                    isRecording = false;

                    const recordBtn = document.getElementById('recordBtn');
                    recordBtn.textContent = '🎤 Record Your Response';
                    recordBtn.className = 'record-btn';

                    updateStatus('📝 Processing your speech...', 'processing');
                    showVisualizer(false);
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
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    stream = null;
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
    """WebSocket endpoint with actual audio support."""
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
                    "customer_name": "valued customer",
                    "product_type": "Auto Loan",
                })

                state.add_turn("bot", initial_response)

                await websocket.send_text(json.dumps({
                    "type": "session_started",
                    "session_id": session_id,
                    "message": initial_response,
                }))

            elif action == "audio_input":
                if not state or not engine:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "No active session"
                    }))
                    continue

                # Decode base64 audio
                audio_data = message.get("audio_data", "")
                audio_format = message.get("format", "webm")

                try:
                    # Decode base64
                    audio_bytes = base64.b64decode(audio_data)

                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_audio:
                        temp_audio.write(audio_bytes)
                        temp_audio_path = temp_audio.name

                    # Convert webm to wav if needed (faster-whisper expects wav/mp3/etc)
                    # For now, we'll try to transcribe directly
                    # In production, you'd use ffmpeg to convert: webm → wav

                    # Transcribe audio
                    logger.info(f"Transcribing audio file: {temp_audio_path}")
                    transcription_result = transcribe_audio(temp_audio_path, language="en")

                    user_text = transcription_result.get("text", "").strip()
                    confidence = abs(transcription_result.get("confidence", 0.5))  # abs because log prob is negative

                    # Clean up temp file
                    Path(temp_audio_path).unlink(missing_ok=True)

                    if not user_text:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Could not transcribe audio. Please try again."
                        }))
                        continue

                    # Send transcription back
                    await websocket.send_text(json.dumps({
                        "type": "transcription",
                        "text": user_text,
                        "confidence": confidence,
                    }))

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

                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Audio processing failed: {str(e)}"
                    }))

            elif action == "end":
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "bot_audio_tester", "audio_support": True}


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🎤 CollectOS Bot Audio Tester")
    print("="*60)
    print("\n📍 Starting server on http://localhost:8080")
    print("\n🎙️  Features:")
    print("   - Real microphone input")
    print("   - Live speech-to-text transcription")
    print("   - Browser text-to-speech playback")
    print("   - Full conversation flow\n")
    print("⚠️  Make sure to grant microphone permission when prompted!\n")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
