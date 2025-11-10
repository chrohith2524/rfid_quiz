from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import random, time, json, os

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

# ------------------- Game State -------------------
state = {
    "category": "Letters",
    "mode": "Sequential",
    "queue": [],
    "current": None,
    "score": 0,
    "total": 0,
    "start": None
}

DB_FILE = "games.json"

# ------------------- Game Storage -------------------
def load_games():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return []

def save_game(entry):
    data = load_games()
    data.append(entry)
    data = data[-5:]  # keep last 5
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ------------------- Helpers -------------------
def items_for(cat):
    if cat == "Letters":
        return list(letter_to_word.keys())
    if cat == "Numbers":
        return [str(i) for i in range(11)]
    return list(shape_uids.values())

# ✅ Category-based UID resolver
def resolve(uid, cat):
    if cat == "Letters":
        return letter_uids.get(uid)
    if cat == "Numbers":
        return number_uids.get(uid)
    if cat == "Shapes":
        return shape_uids.get(uid)
    return None

def emit_update(msg, stat, extra=None):
    data = {
        "msg": msg,
        "stat": stat,
        "cat": state["category"],
        "item": state["current"],
        "score": state["score"],
        "total": state["total"]
    }
    if extra:
        data.update(extra)
    socketio.emit("update", data)

def next_item():
    if state["queue"]:
        state["current"] = state["queue"].pop(0)
    else:
        # Game finished
        duration = round(time.time() - state["start"], 1)
        state["current"] = None
        emit_update("✅ Quiz Finished!", "done", {"duration": duration})
        # Save result
        save_game({
            "category": state["category"],
            "score": state["score"],
            "total": state["total"],
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": f"{duration}s"
        })

def start_game(cat, mode):
    q = items_for(cat)
    if mode == "Random":
        random.shuffle(q)
    state.update(category=cat, mode=mode, queue=q,
                 score=0, total=len(q), start=time.time())
    next_item()
    emit_update("Game started!", "neutral")

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

    if not state["current"]:
        emit_update("✅ Quiz Finished!", "done")

    elif item == state["current"]:
        state["score"] += 1
        next_item()  # ✅ move to next before emitting
        emit_update("✅ Correct!", "ok")
        print(f"[DEBUG] Next item: {state['current']}")

    else:
        print(f"[DEBUG] UID {uid} resolved to {item} in {cat}, expected {state['current']}")
        emit_update("❌ Wrong! Try again", "wrong")

    return jsonify(ok=True)

@app.route("/api/games")
def get_games():
    return jsonify(load_games())

@socketio.on("connect")
def connect():
    emit_update("Connected", "neutral")

# ------------------- HTML PAGE -------------------
HTML_PAGE = """<!doctype html><html><head>
<meta charset="utf-8"><title>RFID Quiz Local</title>
<style>
body{font-family:Segoe UI,Arial;background:#eef3f9;margin:0;text-align:center}
h1{margin:20px 0}
select,button{padding:8px 12px;font-size:16px;margin:5px}
.stage{margin:20px auto;padding:20px;background:#fff;border-radius:16px;
       width:320px;box-shadow:0 6px 20px rgba(0,0,0,0.08)}
.big{font-size:72px}
#pic{width:220px;height:220px;object-fit:contain;border-radius:12px;background:#f6f8fb;margin-top:10px}
.ok-flash{animation:ok 0.6s ease}
.wrong-flash{animation:wrong 0.6s ease}
@keyframes ok{0%{background:#e8ffe8}100%{background:#fff}}
@keyframes wrong{0%{background:#ffe8e8}100%{background:#fff}}
.ok{color:green}.wrong{color:red}.neutral{color:#555}.done{color:#0b6e99;font-weight:600}
table{margin:20px auto;border-collapse:collapse;width:90%;max-width:500px}
th,td{border:1px solid #ccc;padding:6px}
</style></head><body>
<h1>RFID Quiz (Local)</h1>
<div>
 Category:<select id=c><option>Letters</option><option>Numbers</option><option>Shapes</option></select>
 Mode:<select id=m><option>Sequential</option><option>Random</option></select>
 <button id=start>Start Game</button>
</div>
<h2 id=status class=neutral>Waiting...</h2>
<div class=stage><div id=item class=big></div><img id=pic src=""></div>
<h3 id=score>Score: 0/0</h3>

<h2>Last 5 Games</h2>
<table id=history>
<thead><tr><th>#</th><th>Category</th><th>Score</th><th>Time</th><th>Duration</th></tr></thead>
<tbody></tbody>
</table>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const s=io(),st=document.getElementById('status'),it=document.getElementById('item'),
sc=document.getElementById('score'),btn=document.getElementById('start'),
cat=document.getElementById('c'),mod=document.getElementById('m'),pic=document.getElementById('pic'),
hist=document.querySelector('#history tbody');

function speak(t){if('speechSynthesis'in window){let u=new SpeechSynthesisUtterance(t);u.lang='en-IN';speechSynthesis.cancel();speechSynthesis.speak(u);}}
function phrase(cat,i){if(cat==='Letters'){const w={A:'Apple',B:'Ball',C:'Cat',D:'Duck',E:'Egg',F:'Frog',G:'Goat',H:'House',I:'Ice Cream',J:'Jug',K:'Kite'};return i+' for '+(w[i]||'');}return i;}
function flash(ok){const stg=document.querySelector('.stage');stg.classList.remove('ok-flash','wrong-flash');void stg.offsetWidth;stg.classList.add(ok?'ok-flash':'wrong-flash');}
btn.onclick=async()=>{await fetch('/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:cat.value,mode:mod.value})});};

s.on('update',d=>{
  st.textContent=d.msg;st.className=d.stat;
  sc.textContent=`Score: ${d.score}/${d.total}`;
  it.textContent=d.item||'';pic.src=d.item?'/static/images/'+d.item+'.jpg':'';
  if(d.item)speak(phrase(d.cat,d.item));
  if(d.stat==='ok')flash(true);if(d.stat==='wrong')flash(false);
  if(d.stat==='done'){loadHistory();showCompletionBanner(d.duration);}
});

async function loadHistory(){
  const r=await fetch('/api/games');
  const rows=await r.json();
  hist.innerHTML=rows.map((g,i)=>`<tr><td>${i+1}</td><td>${g.category}</td><td>${g.score}/${g.total}</td><td>${g.time}</td><td>${g.duration||'-'}</td></tr>`).join('');
}
loadHistory();

function showCompletionBanner(duration){
  speak("Quiz Completed!");
  const banner=document.createElement('div');
  banner.innerHTML=`
    <div style="position:fixed;inset:0;background:rgba(0,0,0,0.7);
      display:flex;justify-content:center;align-items:center;flex-direction:column;
      color:white;z-index:9999;">
      <h1>🎉 QUIZ COMPLETED!</h1>
      <h3>${sc.textContent}</h3>
      <p>⏱️ Time taken: ${duration}s</p>
      <button onclick="this.parentElement.parentElement.remove()"
        style="padding:10px 20px;border:none;border-radius:10px;background:#6ee7ff;color:black;font-weight:bold;cursor:pointer;">
        OK
      </button>
    </div>`;
  document.body.appendChild(banner);
}
</script></body></html>"""

# ------------------- Run -------------------
if __name__ == "__main__":
    start_game("Letters", "Sequential")
    socketio.run(app, host="0.0.0.0", port=5050, debug=True)
