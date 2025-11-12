from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import random, time, json, os
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------- RFID UID Maps -------------------
letter_uids = {
    "35278F02": "A", "A3624B39": "B", "93B09239": "C", "436F7733": "D",
    "F3C48333": "E", "234F4F39": "F", "2F2499DA": "G", "F2910C01": "H",
    "62A60901": "I", "E2B81201": "J", "C26F0901": "K"
}
number_uids = {
    "35278F02": "0", "A3624B39": "1", "93B09239": "2", "436F7733": "3",
    "F3C48333": "4", "234F4F39": "5", "2F2499DA": "6", "F2910C01": "7",
    "62A60901": "8", "E2B81201": "9", "C26F0901": "10"
}
shape_uids = {
    "35278F02": "Circle", "A3624B39": "Rectangle",
    "93B09239": "Triangle", "436F7733": "Square"
}

letter_to_word = {
    "A": "Apple", "B": "Ball", "C": "Cat", "D": "Duck", "E": "Egg",
    "F": "Frog", "G": "Goat", "H": "House", "I": "Ice Cream",
    "J": "Jug", "K": "Kite"
}

HISTORY_FILE = "games.json"

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

# ------------------- History Helpers -------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ------------------- Game Helpers -------------------
def items_for(cat):
    if cat == "Letters":
        return list(letter_to_word.keys())
    if cat == "Numbers":
        return [str(i) for i in range(11)]
    if cat == "Shapes":
        return list(shape_uids.values())
    return []

def resolve(uid, category):
    if category == "Letters":
        return letter_uids.get(uid)
    if category == "Numbers":
        return number_uids.get(uid)
    if category == "Shapes":
        return shape_uids.get(uid)
    return None

def emit_update(msg, stat):
    socketio.emit("update", {
        "msg": msg,
        "stat": stat,
        "cat": state["category"],
        "item": state["current"],
        "score": state["score"],
        "total": state["total"],
        "history": load_history()
    })

def next_item():
    if state["queue"]:
        state["current"] = state["queue"].pop(0)
    else:
        state["current"] = None
        finish_game()

def start_game(cat, mode):
    q = items_for(cat)
    if mode == "Random":
        random.shuffle(q)
    state.update(
        category=cat, mode=mode, queue=q.copy(),
        score=0, total=len(q), start=time.time(), finished=False
    )
    next_item()
    emit_update("Game started!", "neutral")

def finish_game():
    if state["finished"]:
        return
    state["finished"] = True
    duration = round(time.time() - state["start"], 2)
    date_played = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    emit_update(f"🏁 Quiz Completed in {duration} sec!", "done")

    hist = load_history()
    hist.insert(0, {
        "category": state["category"],
        "score": state["score"],
        "total": state["total"],
        "time": duration,
        "date": date_played
    })
    save_history(hist[:5])

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
    uid = request.get_json(force=True).get("uid", "").upper()
    cat = state["category"]
    item = resolve(uid, cat)

    print(f"[SCAN] UID {uid} -> {item} (cat={cat}) expect {state['current']}")

    if not state["current"]:
        finish_game()
    elif item == state["current"]:
        state["score"] += 1
        next_item()
        if state["current"] is None:
            finish_game()
        else:
            emit_update("✅ Correct!", "ok")
    else:
        emit_update("❌ Wrong! Try again", "wrong")

    return jsonify(ok=True)

@socketio.on("connect")
def connect():
    emit_update("Connected", "neutral")

# ------------------- HTML -------------------
HTML_PAGE = """<!doctype html><html><head>
<meta charset="utf-8"><title>RFID Quiz</title>
<style>
body{font-family:Segoe UI,Arial;background:#eef3f9;margin:0;text-align:center}
h1{margin:20px 0}
select,button{padding:8px 12px;font-size:16px;margin:5px}
.stage{margin:20px auto;padding:20px;background:#fff;border-radius:16px;width:340px;box-shadow:0 6px 20px rgba(0,0,0,0.08)}
.big{font-size:72px}
#pic{width:220px;height:220px;object-fit:contain;border-radius:12px;background:#f6f8fb;margin-top:10px;transition:opacity .3s ease;opacity:0}
table{margin:auto;width:85%;border-collapse:collapse;margin-top:20px;max-width:750px}
th,td{padding:8px;border-bottom:1px solid #ccc;text-align:center}
thead{background:#0b6e99;color:white}
.ok-flash{animation:ok 0.5s ease}
.wrong-flash{animation:wrong 0.5s ease}
@keyframes ok{0%{background:#e8ffe8}100%{background:#fff}}
@keyframes wrong{0%{background:#ffe8e8}100%{background:#fff}}
.ok{color:green}.wrong{color:red}.neutral{color:#555}.done{color:#0b6e99;font-weight:600}
.highlight{background:#e3f2fd;font-weight:bold}
</style></head><body>
<h1>RFID Quiz Learning</h1>
<div>
  Category:
  <select id=c>
    <option>Letters</option>
    <option>Numbers</option>
    <option>Shapes</option>
  </select>
  Mode:
  <select id=m>
    <option>Sequential</option>
    <option>Random</option>
  </select>
  <button id=start>Start Game</button>
</div>

<h2 id=status class=neutral>Waiting...</h2>
<div class=stage>
  <div id=item class=big></div>
  <img id=pic src="">
</div>
<h3 id=score>Score: 0/0</h3>

<h2>📊 Last 5 Games</h2>
<table>
  <thead><tr><th>Category</th><th>Score</th><th>Time (sec)</th><th>Date</th></tr></thead>
  <tbody id=hist></tbody>
</table>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
// ✅ Preload images to remove lag
const preloadImages = () => {
  const imgs = ['A','B','C','D','E','F','G','H','I','J','K',
    '0','1','2','3','4','5','6','7','8','9','10',
    'Circle','Rectangle','Triangle','Square'];
  imgs.forEach(i => {const img=new Image();img.src='/static/images/'+i+'.jpg';});
};
window.onload = preloadImages;

const s=io(),st=document.getElementById('status'),it=document.getElementById('item'),
sc=document.getElementById('score'),btn=document.getElementById('start'),
cat=document.getElementById('c'),mod=document.getElementById('m'),
pic=document.getElementById('pic'),hist=document.getElementById('hist');

function speak(t){if('speechSynthesis'in window){let u=new SpeechSynthesisUtterance(t);u.lang='en-IN';speechSynthesis.cancel();speechSynthesis.speak(u);}}
function phrase(cat,i){
  if(cat==='Letters'){const w={A:'Apple',B:'Ball',C:'Cat',D:'Duck',E:'Egg',F:'Frog',G:'Goat',H:'House',I:'Ice Cream',J:'Jug',K:'Kite'};return i+' for '+(w[i]||'');}
  if(cat==='Numbers'){const n={"0":"Zero","1":"One","2":"Two","3":"Three","4":"Four","5":"Five","6":"Six","7":"Seven","8":"Eight","9":"Nine","10":"Ten"};return n[i]||i;}
  return i;
}

function renderHistory(list){hist.innerHTML=list.map((x,i)=>`<tr class='${i===0?"highlight":""}'><td>${x.category}</td><td>${x.score}/${x.total}</td><td>${x.time}</td><td>📅 ${x.date||"-"}</td></tr>`).join('');}

btn.onclick=async()=>{await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat.value,mode:mod.value})});};

s.on('update',d=>{
  st.textContent=d.msg;st.className=d.stat;
  sc.textContent=`Score: ${d.score}/${d.total}`;
  it.textContent=d.item||'';
  if(d.item){pic.style.opacity=0;setTimeout(()=>{pic.src='/static/images/'+d.item+'.jpg';pic.style.opacity=1;speak(phrase(d.cat,d.item));},200);}
  renderHistory(d.history||[]);
});
</script></body></html>"""

# ------------------- Run -------------------
if __name__ == "__main__":
    start_game("Letters", "Sequential")
    socketio.run(app, host="0.0.0.0", port=5050, debug=True)
