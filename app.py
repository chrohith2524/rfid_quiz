from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_socketio import SocketIO
import random, time, os, json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------- Local DB -------------------
DB_FILE = "games.json"
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: 
            return json.load(f)
    return {"games": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ------------------- RFID UID Mappings -------------------
letter_uids = {
    "35278F02":"A","A3624B39":"B","93B09239":"C","436F7733":"D",
    "F3C48333":"E","234F4F39":"F","2F2499DA":"G","F2910C01":"H",
    "62A60901":"I","E2B81201":"J","C26F0901":"K"
}
number_uids = {
    "35278F02":"0","A3624B39":"1","93B09239":"2","436F7733":"3",
    "F3C48333":"4","234F4F39":"5","2F2499DA":"6","F2910C01":"7",
    "62A60901":"8","E2B81201":"9","C26F0901":"10"
}
shape_uids = {
    "35278F02":"Circle","A3624B39":"Rectangle",
    "93B09239":"Triangle","436F7733":"Square"
}
letter_to_word = {
    "A":"Apple","B":"Ball","C":"Cat","D":"Duck","E":"Egg",
    "F":"Frog","G":"Goat","H":"House","I":"Ice Cream",
    "J":"Jug","K":"Kite"
}

# ------------------- Game State -------------------
state = {
    "category": "Letters",
    "mode": "Sequential",
    "queue": [],
    "current": None,
    "score": 0,
    "total": 0,
    "start": None,
    "finished": False
}

# ------------------- Helper Functions -------------------
def items_for(cat):
    if cat == "Letters": return list(letter_to_word.keys())
    if cat == "Numbers": return [str(i) for i in range(11)]
    if cat == "Shapes": return list(shape_uids.values())
    return []

def resolve(uid):
    cat = state["category"]
    if cat == "Letters": return letter_uids.get(uid)
    if cat == "Numbers": return number_uids.get(uid)
    if cat == "Shapes": return shape_uids.get(uid)
    return None

def emit_update(msg, stat):
    socketio.emit("update", {
        "msg": msg,
        "stat": stat,
        "cat": state["category"],
        "item": state["current"],
        "score": state["score"],
        "total": state["total"]
    })

def next_item():
    if state["queue"]:
        state["current"] = state["queue"].pop(0)
        emit_update("Next item", "neutral")
    else:
        duration = round(time.time() - state["start"], 2)
        state["current"] = None
        state["finished"] = True
        data = load_db()
        data["games"].append({
            "category": state["category"],
            "score": state["score"],
            "total": state["total"],
            "time": duration
        })
        data["games"] = data["games"][-5:]
        save_db(data)
        emit_update(f"✅ Quiz Finished in {duration}s!", "done")

def start_game(cat, mode):
    q = items_for(cat)
    if mode == "Random":
        random.shuffle(q)
    state.update(category=cat, mode=mode, queue=q, score=0,
                 total=len(q), start=time.time(), finished=False)
    next_item()

# ------------------- Routes -------------------
@app.route("/")
def home(): 
    return render_template_string(HTML_PAGE)

@app.route("/start", methods=["POST"])
def start():
    d = request.get_json(force=True)
    start_game(d.get("category", "Letters"), d.get("mode", "Sequential"))
    return jsonify(ok=True)

@app.route("/scan", methods=["POST"])
def scan():
    body = request.get_json(force=True)
    uid = body.get("uid", "").upper()
    category = body.get("category", state["category"])
    state["category"] = category

    if state["finished"]:
        emit_update("✅ Quiz already finished!", "done")
        return jsonify(ok=True)

    item = resolve(uid)
    print(f"🔍 UID={uid} | Category={category} | Resolved={item} | Current={state['current']}")

    if not item:
        emit_update("⚠️ Unknown card!", "wrong")
        return jsonify(ok=True)

    if item == state["current"]:
        state["score"] += 1
        emit_update("✅ Correct!", "ok")
        next_item()
    else:
        emit_update("❌ Wrong! Try again", "wrong")

    return jsonify(ok=True)

@app.route("/api/games")
def games(): 
    return jsonify(load_db()["games"])

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

@socketio.on("connect")
def connect():
    emit_update("Connected", "neutral")

# ------------------- HTML Frontend -------------------
HTML_PAGE = """<!doctype html><html><head>
<meta charset="utf-8"><title>RFID Quiz</title>
<style>
body{font-family:Segoe UI,Arial;background:#eef3f9;margin:0;text-align:center}
h1{margin:20px 0}
select,button{padding:8px 12px;font-size:16px;margin:5px}
.stage{margin:20px auto;padding:20px;background:#fff;border-radius:16px;
width:320px;box-shadow:0 6px 20px rgba(0,0,0,0.08)}
.big{font-size:72px}
#pic{width:220px;height:220px;object-fit:contain;border-radius:12px;background:#f6f8fb;margin-top:10px}
.ok-flash{animation:ok 0.4s ease}
.wrong-flash{animation:wrong 0.4s ease}
@keyframes ok{0%{background:#e8ffe8}100%{background:#fff}}
@keyframes wrong{0%{background:#ffe8e8}100%{background:#fff}}
.ok{color:green}.wrong{color:red}.neutral{color:#555}.done{color:#0b6e99;font-weight:600}
audio{display:none}
</style></head><body>
<h1>RFID Quiz</h1>
<div>
Category:<select id=c><option>Letters</option><option>Numbers</option><option>Shapes</option></select>
Mode:<select id=m><option>Sequential</option><option>Random</option></select>
<button id=start>Start Game</button>
</div>
<h2 id=status class=neutral>Waiting...</h2>
<div class=stage><div id=item class=big></div><img id=pic src=""></div>
<h3 id=score>Score: 0/0</h3>
<h2>🕹️ Last 5 Games</h2>
<table style="margin:auto;border-collapse:collapse">
<thead><tr><th>Category</th><th>Score</th><th>Total</th><th>Time(s)</th></tr></thead>
<tbody id=history></tbody></table>

<audio id=ding src="https://cdn.pixabay.com/download/audio/2021/08/04/audio_c3f9b1e982.mp3?filename=correct-answer-6033.mp3"></audio>
<audio id=buzz src="https://cdn.pixabay.com/download/audio/2021/08/09/audio_0b19ff9931.mp3?filename=error-126627.mp3"></audio>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const s=io(),st=document.getElementById('status'),it=document.getElementById('item'),
sc=document.getElementById('score'),btn=document.getElementById('start'),
cat=document.getElementById('c'),mod=document.getElementById('m'),pic=document.getElementById('pic'),
history=document.getElementById('history'),ding=document.getElementById('ding'),
buzz=document.getElementById('buzz');

async function loadHistory(){
 const r=await fetch('/api/games');const data=await r.json();
 history.innerHTML=data.map(g=>`<tr><td>${g.category}</td><td>${g.score}</td><td>${g.total}</td><td>${g.time}</td></tr>`).join('');
}

function speak(t){if('speechSynthesis'in window){let u=new SpeechSynthesisUtterance(t);u.lang='en-IN';speechSynthesis.cancel();speechSynthesis.speak(u);}}

btn.onclick=async()=>{await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({category:cat.value,mode:mod.value})});};

s.on('update',d=>{
 st.textContent=d.msg;st.className=d.stat;
 sc.textContent=`Score: ${d.score}/${d.total}`;
 it.textContent=d.item||'';pic.src=d.item?'/static/images/'+d.item+'.jpg':'';
 if(d.item){if(d.cat==='Letters'){const w={A:'Apple',B:'Ball',C:'Cat',D:'Duck',E:'Egg',F:'Frog',G:'Goat',H:'House',I:'Ice Cream',J:'Jug',K:'Kite'};speak(d.item+' for '+(w[d.item]||''));}else{speak(d.item);}}
 if(d.stat==='ok'){ding.play();speak('Correct!');}
 if(d.stat==='wrong'){buzz.play();speak('Wrong! Try again');}
 if(d.stat==='done'){speak('Quiz Finished!');loadHistory();}
});
loadHistory();
</script></body></html>"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",5050))
    socketio.run(app,host="0.0.0.0",port=port,debug=True)
