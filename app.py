from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import random, time, json
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------- RFID UID Maps -------------------
letter_uids = {
    "35278F02": "A", "A3624B39": "B", "93B09239": "C", "436F7733": "D",
    "F3C48333": "E", "234F4F39": "F", "2F2499DA": "G", "F2910C01": "H",
    "62A60901": "I", "E2B81201": "J", "C26F0901": "K"
}
number_uids = {uid: str(i) for i, uid in enumerate(letter_uids.keys())}
shape_uids = {
    "35278F02": "Circle", "A3624B39": "Rectangle",
    "93B09239": "Triangle", "436F7733": "Square"
}

letter_to_word = {
    "A": "Apple", "B": "Ball", "C": "Cat", "D": "Duck", "E": "Egg",
    "F": "Frog", "G": "Goat", "H": "House", "I": "Ice Cream",
    "J": "Jug", "K": "Kite"
}

# ------------------- Game State -------------------
state = {"category": "Letters", "mode": "Sequential", "queue": [],
         "current": None, "score": 0, "total": 0, "start": None}

HISTORY_FILE = "history.json"

def load_history():
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except:
        return []

def save_history(hist):
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist[-5:], f, indent=2)

history = load_history()

def items_for(cat):
    if cat == "Letters": return list(letter_to_word.keys())
    if cat == "Numbers": return [str(i) for i in range(11)]
    return list(shape_uids.values())

def resolve(uid):
    return letter_uids.get(uid) or number_uids.get(uid) or shape_uids.get(uid)

def emit_update(msg, stat):
    socketio.emit("update", {
        "msg": msg, "stat": stat, "cat": state["category"],
        "item": state["current"], "score": state["score"], "total": state["total"]
    })

def next_item():
    if state["queue"]:
        state["current"] = state["queue"].pop(0)
    else:
        duration = int(time.time() - state["start"])
        completed = {
            "category": state["category"],
            "score": state["score"],
            "total": state["total"],
            "duration": duration,
            "date": datetime.now().strftime("%d %b %Y, %I:%M %p")
        }
        history.append(completed)
        save_history(history)
        emit_update(f"✅ Quiz Completed in {duration}s!", "done")
        state["current"] = None

def start_game(cat, mode):
    q = items_for(cat)
    if mode == "Random": random.shuffle(q)
    state.update(category=cat, mode=mode, queue=q, score=0, total=len(q), start=time.time())
    next_item()
    emit_update("Game started!", "neutral")

@app.route("/")
def home():
    return render_template_string(HTML_PAGE, history=history)

@app.route("/start", methods=["POST"])
def start():
    d = request.get_json(force=True)
    start_game(d.get("category", "Letters"), d.get("mode", "Sequential"))
    return jsonify(ok=True)

@app.route("/scan", methods=["POST"])
def scan():
    uid = request.get_json(force=True).get("uid", "").upper()
    item = resolve(uid)
    if not state["current"]:
        emit_update("✅ Quiz Finished!", "done")
    elif item == state["current"]:
        state["score"] += 1
        emit_update("✅ Correct!", "ok")
        next_item()
    else:
        emit_update("❌ Wrong! Try again", "wrong")
    return jsonify(ok=True)

# ------------------- HTML PAGE -------------------
HTML_PAGE = """<!doctype html><html><head>
<meta charset="utf-8"><title>RFID Quiz</title>
<style>
body{font-family:Segoe UI;background:#eef3f9;text-align:center}
h1{margin:15px 0}
.stage{margin:20px auto;padding:20px;background:#fff;border-radius:16px;
width:320px;box-shadow:0 6px 20px rgba(0,0,0,0.08)}
#pic{width:220px;height:220px;object-fit:contain;border-radius:12px;background:#f6f8fb;margin-top:10px}
.ok{color:green}.wrong{color:red}.done{color:#0b6e99;font-weight:600}
table{margin:20px auto;border-collapse:collapse}
th,td{border:1px solid #aaa;padding:6px 10px}
th{background:#ddd}
</style></head><body>
<h1>RFID Quiz</h1>
<div>
Category:<select id=c><option>Letters</option><option>Numbers</option><option>Shapes</option></select>
Mode:<select id=m><option>Sequential</option><option>Random</option></select>
<button id=start>Start Game</button>
</div>
<h2 id=status class=neutral>Waiting...</h2>
<div class=stage><div id=item style="font-size:70px"></div><img id=pic src=""></div>
<h3 id=score>Score: 0/0</h3>
<h2>🎮 Last 5 Games</h2>
<table><tr><th>Category</th><th>Score</th><th>Total</th><th>Duration</th><th>Date</th></tr>
{% for g in history %}
<tr><td>{{g.category}}</td><td>{{g.score}}</td><td>{{g.total}}</td><td>{{g.duration}}s</td><td>{{g.date}}</td></tr>
{% endfor %}
</table>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const s=io(),st=document.getElementById('status'),it=document.getElementById('item'),
sc=document.getElementById('score'),btn=document.getElementById('start'),
cat=document.getElementById('c'),mod=document.getElementById('m'),pic=document.getElementById('pic');
function speak(t){if('speechSynthesis'in window){let u=new SpeechSynthesisUtterance(t);u.lang='en-IN';speechSynthesis.cancel();speechSynthesis.speak(u);}}
function phrase(cat,i){if(cat==='Letters'){const w={A:'Apple',B:'Ball',C:'Cat',D:'Duck',E:'Egg',F:'Frog',G:'Goat',H:'House',I:'Ice Cream',J:'Jug',K:'Kite'};return i+' for '+(w[i]||'');}return i;}
btn.onclick=async()=>{await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat.value,mode:mod.value})});};
s.on('update',d=>{st.textContent=d.msg;st.className=d.stat;sc.textContent=`Score: ${d.score}/${d.total}`;it.textContent=d.item||'';pic.src=d.item?'/static/images/'+d.item+'.jpg':'';if(d.item)speak(phrase(d.cat,d.item));});
</script></body></html>"""

# ------------------- Run -------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=True)
