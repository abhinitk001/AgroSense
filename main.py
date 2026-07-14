# main.py - Complete Working Version

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import json
import uuid
import logging
from datetime import datetime
from typing import Dict

from database import Base, engine
from auth import router as auth_router
from sensor import router as sensor_router
from ai.crop_ai import router as crop_ai_router
from ai.fertilizer_ai import router as fertilizer_router
from market import router as market_router
from alerts import router as alerts_router
from disease import router as disease_router
from weather import router as weather_router
from crop_recommendation import router as crop_recommendation_router
from market_cache import update_market_cache
import os

# ==========================================================
# PUBLIC SERVER CONFIG
# ==========================================================
# CRITICAL: A phone on 5G/cellular data is NOT on your local WiFi/LAN.
# A hardcoded LAN IP like 192.168.1.124 is invisible to it. This must
# be a hostname/IP that is actually reachable from the public internet
# (a domain name behind a reverse proxy, a cloud VM's public IP, or a
# tunnel like ngrok/Cloudflare Tunnel while testing).
#
# Set these via environment variables so you don't have to edit code
# every time your network changes:
#   PUBLIC_HOST=yourdomain.com   (or ngrok host, or public IP)
#   PUBLIC_PORT=443              (443 if behind HTTPS reverse proxy)
#   PUBLIC_SCHEME=https          (must be https for camera + wss to work
#                                  off localhost)
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "127.0.0.1")
PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", "8000"))
PUBLIC_SCHEME = os.getenv("PUBLIC_SCHEME", "http")  # "https" in production/5G use

# Optional TURN server (needed almost always for a cellular device, see
# NETWORK_SETUP.md). Leave blank to fall back to STUN-only (works only
# on friendly networks, will usually fail over real 5G/CGNAT).
TURN_URL = os.getenv("TURN_URL", "")
TURN_USERNAME = os.getenv("TURN_USERNAME", "")
TURN_CREDENTIAL = os.getenv("TURN_CREDENTIAL", "")


def public_base_url() -> str:
    return f"{PUBLIC_SCHEME}://{PUBLIC_HOST}:{PUBLIC_PORT}" if PUBLIC_PORT not in (80, 443) \
        else f"{PUBLIC_SCHEME}://{PUBLIC_HOST}"


def ice_servers_config() -> list:
    servers = [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]
    if TURN_URL:
        servers.append({
            "urls": TURN_URL,
            "username": TURN_USERNAME,
            "credential": TURN_CREDENTIAL,
        })
    return servers

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================================
# CREATE DATABASE TABLES
# ==========================================================

Base.metadata.create_all(bind=engine)

# ==========================================================
# CREATE FASTAPI APP
# ==========================================================

app = FastAPI(
    title="5G Agro Sense",
    version="1.0.0"
)

# ==========================================================
# STATIC FILES
# ==========================================================

app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================================================
# HTML TEMPLATES
# ==========================================================

templates = Jinja2Templates(directory="templates")

# ==========================================================
# WEBRTC CONNECTION MANAGER
# ==========================================================

class WebRTCManager:
    def __init__(self):
        self.mobile_connections: Dict[str, dict] = {}
        self.dashboard_connections: Dict[str, WebSocket] = {}
        self.pairings: Dict[str, str] = {}
        self.reverse_pairings: Dict[str, str] = {}
        self.stream_links: Dict[str, dict] = {}
    
    async def connect_mobile(self, websocket: WebSocket, location: str = "Unknown") -> str:
        client_id = f"mobile_{uuid.uuid4().hex[:8]}"
        self.mobile_connections[client_id] = {
            'ws': websocket,
            'location': location,
            'connected_at': datetime.now().isoformat(),
            'last_heartbeat': datetime.now().isoformat()
        }
        logger.info(f"📱 Mobile connected: {client_id} from {location}")
        return client_id
    
    async def connect_dashboard(self, websocket: WebSocket) -> str:
        client_id = f"dashboard_{uuid.uuid4().hex[:8]}"
        self.dashboard_connections[client_id] = websocket
        logger.info(f"💻 Dashboard connected: {client_id}")
        return client_id
    
    def disconnect(self, client_id: str):
        if client_id in self.mobile_connections:
            if client_id in self.pairings:
                dashboard_id = self.pairings[client_id]
                if dashboard_id in self.reverse_pairings:
                    del self.reverse_pairings[dashboard_id]
                del self.pairings[client_id]
            for link_id, link_data in self.stream_links.items():
                if link_data.get('mobile') == client_id:
                    link_data['mobile'] = None
            del self.mobile_connections[client_id]
            logger.info(f"📱 Mobile disconnected: {client_id}")
            
        elif client_id in self.dashboard_connections:
            if client_id in self.reverse_pairings:
                mobile_id = self.reverse_pairings[client_id]
                if mobile_id in self.pairings:
                    del self.pairings[mobile_id]
                del self.reverse_pairings[client_id]
            for link_id, link_data in self.stream_links.items():
                if link_data.get('dashboard') == client_id:
                    link_data['dashboard'] = None
            del self.dashboard_connections[client_id]
            logger.info(f"💻 Dashboard disconnected: {client_id}")
    
    async def pair(self, mobile_id: str, dashboard_id: str) -> bool:
        if mobile_id not in self.mobile_connections:
            logger.warning(f"Mobile {mobile_id} not found for pairing")
            return False
        if dashboard_id not in self.dashboard_connections:
            logger.warning(f"Dashboard {dashboard_id} not found for pairing")
            return False
        
        if mobile_id in self.pairings:
            old_dash = self.pairings[mobile_id]
            if old_dash in self.reverse_pairings:
                del self.reverse_pairings[old_dash]
            del self.pairings[mobile_id]
        
        if dashboard_id in self.reverse_pairings:
            old_mobile = self.reverse_pairings[dashboard_id]
            if old_mobile in self.pairings:
                del self.pairings[old_mobile]
            del self.reverse_pairings[dashboard_id]
        
        self.pairings[mobile_id] = dashboard_id
        self.reverse_pairings[dashboard_id] = mobile_id
        logger.info(f"🔗 Paired {mobile_id} ↔ {dashboard_id}")
        return True
    
    async def forward_to_dashboard(self, mobile_id: str, data: dict) -> bool:
        if mobile_id not in self.pairings:
            logger.warning(f"Mobile {mobile_id} not paired")
            return False
        dashboard_id = self.pairings[mobile_id]
        if dashboard_id not in self.dashboard_connections:
            logger.warning(f"Dashboard {dashboard_id} not connected")
            return False
        try:
            await self.dashboard_connections[dashboard_id].send_text(json.dumps(data))
            logger.info(f"📤 Forwarded {data.get('type')} to dashboard")
            return True
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return False
    
    async def forward_to_mobile(self, dashboard_id: str, data: dict) -> bool:
        if dashboard_id not in self.reverse_pairings:
            logger.warning(f"Dashboard {dashboard_id} not paired")
            return False
        mobile_id = self.reverse_pairings[dashboard_id]
        if mobile_id not in self.mobile_connections:
            logger.warning(f"Mobile {mobile_id} not connected")
            return False
        try:
            await self.mobile_connections[mobile_id]['ws'].send_text(json.dumps(data))
            logger.info(f"📤 Forwarded {data.get('type')} to mobile")
            return True
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return False
    
    def get_available_mobiles(self) -> list:
        return [
            {
                'id': client_id,
                'location': data['location'],
                'connected_at': data['connected_at'],
                'paired': client_id in self.pairings,
                'paired_with': self.pairings.get(client_id)
            }
            for client_id, data in self.mobile_connections.items()
        ]
    
    def generate_stream_link(self) -> dict:
        link_id = uuid.uuid4().hex[:8]
        self.stream_links[link_id] = {
            'mobile': None,
            'dashboard': None,
            'created': datetime.now().isoformat(),
            'active': True
        }
        return {
            'link_id': link_id,
            'mobile_link': f"/livestream/mobile?link={link_id}",
            'full_url': f"{public_base_url()}/livestream/mobile?link={link_id}"
        }

# Create WebRTC manager instance
webrtc_manager = WebRTCManager()

# ==========================================================
# WEBRTC WEBSOCKET ENDPOINTS
# ==========================================================

@app.websocket("/ws/mobile")
async def mobile_websocket(websocket: WebSocket):
    """Mobile WebSocket endpoint for 5G streaming"""
    location = websocket.query_params.get('location', 'Unknown')
    link_id = websocket.query_params.get('link', None)
    
    logger.info(f"📱 Mobile WebSocket attempt from location: {location}")
    
    try:
        await websocket.accept()
        logger.info(f"✅ Mobile WebSocket accepted")
        
        client_id = await webrtc_manager.connect_mobile(websocket, location)
        
        if link_id and link_id in webrtc_manager.stream_links:
            webrtc_manager.stream_links[link_id]['mobile'] = client_id
            logger.info(f"🔗 Mobile {client_id} registered with link {link_id}")
            
            if webrtc_manager.stream_links[link_id]['dashboard']:
                dashboard_id = webrtc_manager.stream_links[link_id]['dashboard']
                if dashboard_id in webrtc_manager.dashboard_connections:
                    await webrtc_manager.pair(client_id, dashboard_id)
                    await webrtc_manager.dashboard_connections[dashboard_id].send_text(json.dumps({
                        'type': 'mobile_connected',
                        'mobile_id': client_id,
                        'location': location,
                        'link_id': link_id
                    }))
        
        await websocket.send_text(json.dumps({
            'type': 'connected',
            'client_id': client_id,
            'location': location,
            'timestamp': datetime.now().isoformat()
        }))
        logger.info(f"📱 Sent connected to {client_id}")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                msg_type = data.get('type', 'unknown')
                
                logger.info(f"📱 Mobile {client_id} → {msg_type}")
                
                if msg_type == 'ping':
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': data.get('timestamp'),
                        'server_time': datetime.now().isoformat()
                    }))
                    if client_id in webrtc_manager.mobile_connections:
                        webrtc_manager.mobile_connections[client_id]['last_heartbeat'] = datetime.now().isoformat()
                
                elif msg_type == 'offer':
                    logger.info(f"📱 Mobile {client_id} sending offer")
                    forwarded = await webrtc_manager.forward_to_dashboard(client_id, {
                        'type': 'offer',
                        'offer': data['offer'],
                        'from': client_id,
                        'location': webrtc_manager.mobile_connections.get(client_id, {}).get('location', 'Unknown')
                    })
                    if forwarded:
                        logger.info(f"📤 Offer forwarded to dashboard")
                    else:
                        logger.warning(f"⚠️ Failed to forward offer - no dashboard paired")
                
                elif msg_type == 'ice_candidate':
                    await webrtc_manager.forward_to_dashboard(client_id, {
                        'type': 'ice_candidate',
                        'candidate': data['candidate'],
                        'from': client_id
                    })
                    logger.info(f"🧊 ICE candidate forwarded")
                
                elif msg_type == 'stream_status':
                    if client_id in webrtc_manager.mobile_connections:
                        webrtc_manager.mobile_connections[client_id]['status'] = data.get('status', 'idle')
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON from {client_id}: {e}")
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.error(f"❌ Error processing message from {client_id}: {e}")
                
    except WebSocketDisconnect:
        logger.info(f"📱 Mobile WebSocket disconnected")
    except Exception as e:
        logger.error(f"❌ Mobile WebSocket error: {e}")
    finally:
        if 'client_id' in locals():
            for link_id, link_data in webrtc_manager.stream_links.items():
                if link_data.get('mobile') == client_id:
                    link_data['mobile'] = None
            webrtc_manager.disconnect(client_id)
            logger.info(f"📱 Cleaned up mobile: {client_id}")

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """Dashboard WebSocket endpoint for 5G streaming"""
    logger.info(f"💻 Dashboard WebSocket attempt")
    
    try:
        await websocket.accept()
        logger.info(f"✅ Dashboard WebSocket accepted")
        
        client_id = await webrtc_manager.connect_dashboard(websocket)
        logger.info(f"💻 Dashboard connected: {client_id}")
        
        await websocket.send_text(json.dumps({
            'type': 'connected',
            'client_id': client_id,
            'available_mobiles': webrtc_manager.get_available_mobiles(),
            'timestamp': datetime.now().isoformat()
        }))
        logger.info(f"💻 Sent connected message to {client_id}")
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                msg_type = data.get('type', 'unknown')
                
                logger.info(f"💻 Dashboard {client_id} → {msg_type}")
                
                if msg_type == 'ping':
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': data.get('timestamp'),
                        'server_time': datetime.now().isoformat()
                    }))
                    logger.info(f"💻 Pong sent to {client_id}")
                
                elif msg_type == 'pair':
                    mobile_id = data.get('mobile_id')
                    if mobile_id:
                        success = await webrtc_manager.pair(mobile_id, client_id)
                        await websocket.send_text(json.dumps({
                            'type': 'paired',
                            'mobile_id': mobile_id,
                            'success': success
                        }))
                        if success:
                            await webrtc_manager.forward_to_mobile(client_id, {
                                'type': 'paired',
                                'dashboard_id': client_id
                            })
                        logger.info(f"💻 Pair result: {success}")
                
                elif msg_type == 'answer':
                    target_mobile = data.get('target')
                    if target_mobile and target_mobile in webrtc_manager.mobile_connections:
                        await webrtc_manager.mobile_connections[target_mobile]['ws'].send_text(json.dumps({
                            'type': 'answer',
                            'answer': data['answer'],
                            'from': client_id
                        }))
                        logger.info(f"💻 Answer forwarded to {target_mobile}")
                
                elif msg_type == 'ice_candidate':
                    target_mobile = data.get('target')
                    if target_mobile and target_mobile in webrtc_manager.mobile_connections:
                        await webrtc_manager.mobile_connections[target_mobile]['ws'].send_text(json.dumps({
                            'type': 'ice_candidate',
                            'candidate': data['candidate'],
                            'from': client_id
                        }))
                        logger.info(f"💻 ICE candidate forwarded to {target_mobile}")
                
                elif msg_type == 'get_mobiles':
                    mobiles = webrtc_manager.get_available_mobiles()
                    await websocket.send_text(json.dumps({
                        'type': 'mobile_list',
                        'mobiles': mobiles
                    }))
                    logger.info(f"💻 Sent mobile list to {client_id}: {len(mobiles)} mobiles")
                
                elif msg_type == 'unpair':
                    mobile_id = data.get('mobile_id')
                    if mobile_id and mobile_id in webrtc_manager.pairings:
                        del webrtc_manager.pairings[mobile_id]
                        if client_id in webrtc_manager.reverse_pairings:
                            del webrtc_manager.reverse_pairings[client_id]
                        await websocket.send_text(json.dumps({
                            'type': 'unpaired',
                            'success': True
                        }))
                        logger.info(f"💻 Unpaired from {mobile_id}")
                
                else:
                    logger.info(f"💻 Unknown message type: {msg_type}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON from {client_id}: {e}")
                continue
            except WebSocketDisconnect:
                logger.info(f"💻 WebSocket disconnected from {client_id}")
                break
            except Exception as e:
                logger.error(f"❌ Error processing message from {client_id}: {e}")
                continue
                
    except WebSocketDisconnect:
        logger.info(f"💻 Dashboard WebSocket disconnected")
    except Exception as e:
        logger.error(f"❌ Dashboard WebSocket error: {e}")
    finally:
        if 'client_id' in locals():
            webrtc_manager.disconnect(client_id)
            logger.info(f"💻 Cleaned up dashboard: {client_id}")

# ==========================================================
# WEBRTC HTTP ENDPOINTS
# ==========================================================

@app.get("/api/stream/generate-link")
async def generate_stream_link():
    link_data = webrtc_manager.generate_stream_link()
    return {
        "success": True,
        "link_id": link_data['link_id'],
        "mobile_link": f"{public_base_url()}{link_data['mobile_link']}",
        "qr_code": f"/api/stream/qr/{link_data['link_id']}",
        "expires_in": "24 hours"
    }

@app.get("/api/stream/qr/{link_id}")
async def generate_qr_code(link_id: str):
    if link_id not in webrtc_manager.stream_links:
        return JSONResponse(status_code=404, content={"error": "Invalid link ID"})
    
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        mobile_url = f"{public_base_url()}/livestream/mobile?link={link_id}"
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(mobile_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return JSONResponse({
            "success": True,
            "link_id": link_id,
            "qr_code": f"data:image/png;base64,{img_str}",
            "mobile_url": mobile_url
        })
    except ImportError:
        return JSONResponse({
            "success": False,
            "error": "qrcode library not installed"
        })

@app.get("/api/stream/status")
async def stream_status():
    return {
        "success": True,
        "mobile_connections": len(webrtc_manager.mobile_connections),
        "dashboard_connections": len(webrtc_manager.dashboard_connections),
        "pairings": len(webrtc_manager.pairings),
        "available_mobiles": webrtc_manager.get_available_mobiles()
    }

# ==========================================================
# INCLUDE ALL ROUTERS
# ==========================================================

app.include_router(auth_router)
app.include_router(sensor_router)
app.include_router(crop_ai_router)
app.include_router(fertilizer_router)
app.include_router(market_router)
app.include_router(alerts_router)
app.include_router(disease_router)
app.include_router(weather_router)
app.include_router(crop_recommendation_router)

# ==========================================================
# BACKGROUND SCHEDULER
# ==========================================================

scheduler = BackgroundScheduler()
scheduler.add_job(update_market_cache, 'interval', minutes=30, id='market_cache_update')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())
print("✅ Market cache scheduler started")

# ==========================================================
# HTML ROUTES
# ==========================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")

@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    return templates.TemplateResponse(request=request, name="analytics.html")

@app.get("/recommendation", response_class=HTMLResponse)
async def recommendation(request: Request):
    return templates.TemplateResponse(request=request, name="recommendation.html")

@app.get("/architecture", response_class=HTMLResponse)
async def architecture(request: Request):
    return templates.TemplateResponse(request=request, name="architecture.html")

@app.get("/livestream", response_class=HTMLResponse)
async def livestream(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="livestream.html",
        context={"ice_servers_json": json.dumps(ice_servers_config())}
    )

@app.get("/livestream/mobile", response_class=HTMLResponse)
async def livestream_mobile(request: Request):
    location = request.query_params.get('location', 'Field A - North')
    link_id = request.query_params.get('link', '')

    return templates.TemplateResponse(
        request=request,
        name="livestream_mobile.html",
        context={
            "location": location,
            "link_id": link_id,
            # kept for backwards compatibility, no longer used to build the
            # WS URL — the page now derives host/protocol from itself
            "server_ip": PUBLIC_HOST,
            "port": PUBLIC_PORT,
            "ice_servers_json": json.dumps(ice_servers_config()),
        }
    )

@app.get("/camera-test-simple", response_class=HTMLResponse)
async def camera_test_simple(request: Request):
    return templates.TemplateResponse(request=request, name="camera_test_simple.html")

@app.get("/ws-test")
async def ws_test():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>WebSocket Test</title></head>
    <body>
        <h1>WebSocket Test</h1>
        <div id="status">Testing...</div>
        <div id="log"></div>
        <script>
            const statusDiv = document.getElementById('status');
            const logDiv = document.getElementById('log');
            function log(msg) { logDiv.innerHTML += msg + '<br>'; console.log(msg); }
            log('🔌 Connecting...');
            const ws = new WebSocket('ws://' + window.location.host + '/ws/dashboard');
            ws.onopen = function() {
                statusDiv.innerHTML = '✅ CONNECTED';
                statusDiv.style.color = 'green';
                log('✅ Connected!');
                ws.send(JSON.stringify({type: 'ping', timestamp: Date.now()}));
            };
            ws.onmessage = function(event) {
                log('📩 ' + event.data);
                const data = JSON.parse(event.data);
                if (data.type === 'pong') {
                    const latency = Date.now() - data.timestamp;
                    log('🏓 Pong! Latency: ' + latency + 'ms');
                }
                if (data.type === 'connected') {
                    log('✅ Client ID: ' + data.client_id);
                }
            };
            ws.onclose = function() { statusDiv.innerHTML = '❌ CLOSED'; statusDiv.style.color = 'red'; };
            ws.onerror = function() { statusDiv.innerHTML = '❌ ERROR'; statusDiv.style.color = 'red'; };
        </script>
    </body>
    </html>
    """)

@app.get("/debug-stream", response_class=HTMLResponse)
async def debug_stream(request: Request):
    return templates.TemplateResponse(request=request, name="debug_stream.html")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "webrtc": {
            "mobile_connections": len(webrtc_manager.mobile_connections),
            "dashboard_connections": len(webrtc_manager.dashboard_connections),
            "pairings": len(webrtc_manager.pairings)
        }
    }

# ==========================================================
# RUN THE APP
# ==========================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🌾 5G AGRO SENSE - WEBRTC INTEGRATED")
    print("="*60)
    print("\n📍 Server running at:")
    print("   http://127.0.0.1:8000")
    print("   http://192.168.1.124:8000")
    print("\n📱 Mobile stream:")
    print("   http://127.0.0.1:8000/livestream/mobile")
    print("\n🖥️ Dashboard stream:")
    print("   http://127.0.0.1:8000/livestream")
    print("\n🔌 WebSocket endpoints:")
    print("   ws://127.0.0.1:8000/ws/mobile")
    print("   ws://127.0.0.1:8000/ws/dashboard")
    print("\n🧪 WebSocket Test:")
    print("   http://127.0.0.1:8000/ws-test")
    print(f"\n📡 Public URL configured as: {public_base_url()}")
    print("   (set PUBLIC_HOST / PUBLIC_PORT / PUBLIC_SCHEME env vars if this is wrong)")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")