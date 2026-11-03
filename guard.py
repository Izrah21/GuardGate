import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template_string, jsonify, session, redirect, url_for
from supabase import create_client, Client

guard_bp = Blueprint('guard_bp', __name__)

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

PH_TZ = timezone(timedelta(hours=8))
CURFEW_HOUR = 20
MAX_ROWS = 20000
LOG_FORMATS = ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p")

GUARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guard Station</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%); }
        .pulse-alert { animation: alert-pulse 1.4s ease-in-out infinite; }
        @keyframes alert-pulse { 50% { box-shadow: 0 0 0 1px rgba(244,63,94,.8), 0 0 42px rgba(244,63,94,.65); } }
        @media (prefers-reduced-motion: reduce) { .pulse-alert { animation: none; } }
    </style>
</head>
<body class="text-slate-800 antialiased min-h-screen p-4 sm:p-6">
    <div id="toast-container" class="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 pointer-events-none max-w-sm w-full"></div>

    <div class="max-w-6xl mx-auto space-y-5">
        <header class="bg-white border border-emerald-900/10 shadow-sm relative z-30 rounded-2xl px-5 py-4 flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                </div>
                <div class="min-w-0">
                    <h1 class="text-xl sm:text-2xl font-bold text-emerald-950 leading-tight">Guard Station</h1>
                    <p class="text-xs text-slate-500 truncate">Dormitory visitor logs and curfew watch</p>
                </div>
            </div>
            <div class="flex items-center gap-3 shrink-0">
                <div class="hidden sm:block text-right">
                    <p id="clock" class="text-sm font-bold text-slate-900">--:--:--</p>
                    <p class="text-[11px] text-slate-500">Curfew <span id="curfew-label">8:00 PM</span></p>
                </div>
                <button id="sound-btn" type="button" onclick="toggleSound()" class="px-3 py-2 text-xs font-semibold text-emerald-800 bg-white border border-emerald-200 rounded-xl hover:bg-emerald-50 transition">Sound off</button>
                <div class="relative">
                    <button id="nav-menu-btn" type="button" onclick="toggleNavMenu(event)" aria-haspopup="true" aria-expanded="false" aria-label="Open menu" class="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center focus:outline-none focus:ring-4 focus:ring-emerald-500/20">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                    </button>
                    <div id="nav-menu-panel" role="menu" class="hidden absolute right-0 top-12 mt-2 w-56 bg-white border border-slate-200 shadow-xl rounded-xl py-1.5 z-50 overflow-hidden">
                        <a href="/scanner" role="menuitem" class="block px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">Student Scanner</a>
                        <a href="/admin-login" role="menuitem" class="block px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">Admin Dashboard</a>
                        <div class="my-1.5 border-t border-slate-200"></div>
                        <a href="/logout" role="menuitem" class="block px-4 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors">Logout</a>
                    </div>
                </div>
            </div>
        </header>

        <section id="alert-banner" class="hidden bg-rose-50 pulse-alert rounded-2xl p-5 border border-rose-300 shadow-lg" role="alert">
            <div class="flex items-start gap-3">
                <div class="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 border border-rose-300 flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                </div>
                <div class="min-w-0 flex-1">
                    <h2 id="alert-title" class="text-sm font-bold text-rose-700"></h2>
                    <p class="text-xs text-rose-700/80 mt-1">These visitors are still timed in after the 8:00 PM curfew. Please check on them.</p>
                    <ul id="alert-list" class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2"></ul>
                </div>
            </div>
        </section>

        <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5">
                <p class="text-xs font-semibold text-slate-500">Inside now</p>
                <p id="stat-inside" class="mt-1 text-3xl font-bold text-slate-900">0</p>
            </div>
            <div class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5">
                <p class="text-xs font-semibold text-slate-500">Past 8:00 PM</p>
                <p id="stat-overdue" class="mt-1 text-3xl font-bold text-rose-600">0</p>
            </div>
            <div class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5">
                <p class="text-xs font-semibold text-slate-500">Total entries logged</p>
                <p id="stat-entries" class="mt-1 text-3xl font-bold text-slate-900">0</p>
            </div>
        </section>

        <section class="grid grid-cols-1 lg:grid-cols-5 gap-5">
            <div class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5 lg:col-span-3 min-w-0">
                <h2 class="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse"></span>
                    Currently inside the dormitory
                </h2>
                <div class="max-h-80 overflow-y-auto">
                    <ul id="inside-list" class="space-y-2"></ul>
                </div>
            </div>
            <div class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5 lg:col-span-2 min-w-0">
                <h2 class="text-sm font-bold text-slate-900 mb-4">Visit frequency</h2>
                <div class="max-h-80 overflow-y-auto">
                    <ul id="frequency-list" class="space-y-2"></ul>
                </div>
            </div>
        </section>

        <section class="bg-white border border-emerald-900/10 shadow-sm rounded-2xl p-5">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
                <h2 class="text-sm font-bold text-slate-900">Visitor logs</h2>
                <div class="flex flex-col sm:flex-row gap-3">
                    <input id="search-input" type="text" oninput="renderLogs()" placeholder="Search name or ID" class="w-full sm:w-64 border border-slate-300 rounded-xl px-3.5 py-2 text-xs outline-none focus:border-emerald-600">
                    <select id="filter-select" onchange="renderLogs()" class="border border-slate-300 rounded-xl px-3.5 py-2 text-xs outline-none focus:border-emerald-600 cursor-pointer">
                        <option value="all">All records</option>
                        <option value="Time In">Time In</option>
                        <option value="Time Out">Time Out</option>
                        <option value="inside">Still inside</option>
                        <option value="overdue">Past 8:00 PM</option>
                    </select>
                </div>
            </div>
            <div class="overflow-x-auto max-h-[28rem] overflow-y-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="border-b border-slate-200 text-slate-400 font-semibold">
                            <th class="p-3">ID Number</th>
                            <th class="p-3">Full Name</th>
                            <th class="p-3">Category / College</th>
                            <th class="p-3">Action</th>
                            <th class="p-3">Timestamp</th>
                        </tr>
                    </thead>
                    <tbody id="logs-tbody"></tbody>
                </table>
            </div>
        </section>
    </div>

    <script>
        let dashboard = { inside: [], logs: [], frequency: [], total_entries: 0 };
        let knownOverdue = null;
        let soundOn = false;
        let audioCtx = null;
        const baseTitle = document.title;

        function escapeHtml(value) {
            return String(value == null ? '' : value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function toggleNavMenu(event) {
            event.stopPropagation();
            const panel = document.getElementById('nav-menu-panel');
            const open = panel.classList.toggle('hidden') === false;
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', String(open));
        }

        function closeNavMenu() {
            document.getElementById('nav-menu-panel').classList.add('hidden');
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', 'false');
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#nav-menu-panel') && !e.target.closest('#nav-menu-btn')) closeNavMenu();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeNavMenu();
        });

        function showToast(message, type) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const tone = type === 'error'
                ? 'bg-rose-50 text-rose-700 border-rose-300 shadow-rose-900/5'
                : 'bg-emerald-50 text-emerald-900 border-emerald-300 shadow-emerald-900/5';
            toast.className = 'pointer-events-auto p-4 rounded-xl shadow-lg border backdrop-blur-xl text-xs font-semibold ' + tone;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 7000);
        }

        function toggleSound() {
            soundOn = !soundOn;
            document.getElementById('sound-btn').innerText = soundOn ? 'Sound on' : 'Sound off';
            if (soundOn) {
                audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
                if (audioCtx.state === 'suspended') audioCtx.resume();
                beep();
            }
        }

        function beep() {
            if (!soundOn || !audioCtx) return;
            [0, 0.28].forEach(function (offset) {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'square';
                osc.frequency.value = 880;
                gain.gain.value = 0.08;
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(audioCtx.currentTime + offset);
                osc.stop(audioCtx.currentTime + offset + 0.18);
            });
        }

        function formatOver(minutes) {
            const h = Math.floor(minutes / 60);
            const m = minutes % 60;
            return h > 0 ? h + 'h ' + m + 'm over' : m + 'm over';
        }

        function renderAlert() {
            const overdue = dashboard.inside.filter(v => v.overdue);
            const banner = document.getElementById('alert-banner');
            document.title = overdue.length ? '(' + overdue.length + ') Curfew alert - Guard Station' : baseTitle;
            if (!overdue.length) {
                banner.classList.add('hidden');
                return;
            }
            banner.classList.remove('hidden');
            document.getElementById('alert-title').innerText = overdue.length === 1
                ? '1 visitor is still inside past 8:00 PM'
                : overdue.length + ' visitors are still inside past 8:00 PM';
            document.getElementById('alert-list').innerHTML = overdue.map(v => `
                <li class="flex items-center justify-between gap-3 rounded-xl bg-rose-50 border border-rose-200 px-3 py-2">
                    <div class="min-w-0">
                        <p class="text-xs font-bold text-slate-900 truncate">${escapeHtml(v.name)}</p>
                        <p class="text-[11px] text-rose-700/80 truncate">${escapeHtml(v.student_id)} | in at ${escapeHtml(v.time_in)}</p>
                    </div>
                    <span class="shrink-0 text-[11px] font-bold text-rose-700">${escapeHtml(formatOver(v.minutes_over))}</span>
                </li>`).join('');
        }

        function notifyNewOverdue() {
            const current = new Set(dashboard.inside.filter(v => v.overdue).map(v => v.student_id));
            if (knownOverdue !== null) {
                const fresh = dashboard.inside.filter(v => v.overdue && !knownOverdue.has(v.student_id));
                if (fresh.length) {
                    fresh.forEach(v => showToast(v.name + ' is still inside past 8:00 PM.', 'error'));
                    beep();
                }
            }
            knownOverdue = current;
        }

        function renderStats() {
            document.getElementById('stat-inside').innerText = dashboard.inside.length;
            document.getElementById('stat-overdue').innerText = dashboard.inside.filter(v => v.overdue).length;
            document.getElementById('stat-entries').innerText = dashboard.total_entries;
        }

        function renderInside() {
            const list = document.getElementById('inside-list');
            if (!dashboard.inside.length) {
                list.innerHTML = '<li class="p-6 text-center text-xs text-slate-400">Nobody is inside right now.</li>';
                return;
            }
            list.innerHTML = dashboard.inside.map(v => `
                <li class="flex items-center justify-between gap-3 rounded-xl px-4 py-3 border ${v.overdue ? 'bg-rose-50 border-rose-300' : 'bg-slate-50 border-slate-200'}">
                    <div class="min-w-0">
                        <p class="text-sm font-semibold text-slate-900 truncate">${escapeHtml(v.name)}</p>
                        <p class="text-[11px] text-slate-400 truncate">${escapeHtml(v.student_id)} | ${escapeHtml(v.college)} | in at ${escapeHtml(v.time_in)}</p>
                    </div>
                    <span class="shrink-0 text-[11px] font-bold px-2.5 py-1 rounded-full border ${v.overdue ? 'bg-rose-100 text-rose-700 border-rose-300' : 'bg-emerald-100 text-emerald-800 border-emerald-200'}">${v.overdue ? escapeHtml(formatOver(v.minutes_over)) : 'Inside'}</span>
                </li>`).join('');
        }

        function renderFrequency() {
            const list = document.getElementById('frequency-list');
            if (!dashboard.frequency.length) {
                list.innerHTML = '<li class="p-6 text-center text-xs text-slate-400">No entries recorded yet.</li>';
                return;
            }
            const top = dashboard.frequency[0].count || 1;
            list.innerHTML = dashboard.frequency.map(v => `
                <li class="rounded-xl bg-slate-50 border border-slate-200 px-4 py-2.5">
                    <div class="flex items-center justify-between gap-3">
                        <p class="text-xs font-semibold text-slate-900 truncate">${escapeHtml(v.name)}</p>
                        <span class="shrink-0 text-xs font-bold text-emerald-800">${v.count}</span>
                    </div>
                    <div class="mt-2 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div class="h-full rounded-full bg-emerald-600" style="width:${Math.round(v.count / top * 100)}%"></div>
                    </div>
                </li>`).join('');
        }

        function renderLogs() {
            const query = document.getElementById('search-input').value.trim().toLowerCase();
            const filter = document.getElementById('filter-select').value;
            const insideIds = new Set(dashboard.inside.map(v => v.log_id));
            const overdueIds = new Set(dashboard.inside.filter(v => v.overdue).map(v => v.log_id));
            const rows = dashboard.logs.filter(row => {
                if (query && !(String(row.student_id).toLowerCase().includes(query) || String(row.name).toLowerCase().includes(query))) return false;
                if (filter === 'Time In' || filter === 'Time Out') return row.action === filter;
                if (filter === 'inside') return insideIds.has(row.id);
                if (filter === 'overdue') return overdueIds.has(row.id);
                return true;
            });
            const tbody = document.getElementById('logs-tbody');
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-400">No matching records.</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(row => `
                <tr class="border-b border-slate-200 hover:bg-emerald-50/30 transition-colors">
                    <td class="p-3 font-semibold text-slate-900">${escapeHtml(row.student_id)}</td>
                    <td class="p-3">${escapeHtml(row.name)}</td>
                    <td class="p-3"><span class="bg-slate-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-semibold">${escapeHtml(row.college)}</span></td>
                    <td class="p-3"><span class="px-2 py-0.5 rounded-full font-semibold border ${row.action === 'Time In' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-slate-100 text-slate-600 border-slate-200'}">${escapeHtml(row.action)}</span></td>
                    <td class="p-3 text-slate-600">${escapeHtml(row.timestamp)}</td>
                </tr>`).join('');
        }

        function renderAll() {
            renderStats();
            renderAlert();
            renderInside();
            renderFrequency();
            renderLogs();
        }

        function loadDashboard() {
            fetch('/api/guard/dashboard')
                .then(r => {
                    if (r.status === 401) { window.location.href = '/guard_login'; return null; }
                    return r.json();
                })
                .then(data => {
                    if (!data) return;
                    dashboard = data;
                    document.getElementById('curfew-label').innerText = data.curfew_label;
                    notifyNewOverdue();
                    renderAll();
                })
                .catch(() => {});
        }

        function tickClock() {
            const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' }));
            document.getElementById('clock').innerText = now.toLocaleTimeString('en-US');
        }

        window.onload = () => {
            tickClock();
            setInterval(tickClock, 1000);
            loadDashboard();
            setInterval(loadDashboard, 10000);
        };
    </script>
</body>
</html>
"""


def parse_timestamp(value):
    text = str(value or "").strip()
    for fmt in LOG_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def pretty_name(raw):
    parts = [p.strip() for p in (raw or "").split(",")]
    parts = [p for p in parts if p and p.upper() != "N/A"]
    if len(parts) <= 1:
        return parts[0] if parts else (raw or "-")
    return f"{parts[0]}, {' '.join(parts[1:])}"


def fetch_all(table, columns, order_column, descending):
    rows = []
    offset = 0
    page = 1000
    while True:
        batch = (
            supabase.table(table)
            .select(columns)
            .order(order_column, desc=descending)
            .range(offset, offset + page - 1)
            .execute()
            .data
            or []
        )
        rows.extend(batch)
        if len(batch) < page or len(rows) >= MAX_ROWS:
            break
        offset += page
    return rows


def format_time(value):
    return value.strftime("%b %d, %I:%M %p").replace(" 0", " ")


@guard_bp.route('/guard')
def guard_page():
    if not session.get('is_guard'):
        return redirect(url_for('guard_login'))
    return render_template_string(GUARD_TEMPLATE)


@guard_bp.route('/api/guard/dashboard')
def guard_dashboard():
    if not session.get('is_guard'):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        now = datetime.now(PH_TZ).replace(tzinfo=None)
        logs = fetch_all("logs", "id,student_id,normalized_name,college,course_year,action,timestamp", "id", True)
    except Exception as e:
        logging.error(f"Guard dashboard load error: {e}")
        return jsonify({"error": "Could not load logs."}), 500

    latest = {}
    entries = {}
    names = {}
    for row in logs:
        s_id = row["student_id"]
        if s_id not in latest:
            latest[s_id] = row
            names[s_id] = pretty_name(row.get("normalized_name"))
        if row["action"] == "Time In":
            entries[s_id] = entries.get(s_id, 0) + 1

    inside = []
    for s_id, row in latest.items():
        if row["action"] != "Time In":
            continue
        time_in = parse_timestamp(row["timestamp"])
        overdue = False
        minutes_over = 0
        if time_in is not None:
            curfew = time_in.replace(hour=CURFEW_HOUR, minute=0, second=0, microsecond=0)
            if now > curfew:
                overdue = True
                minutes_over = int((now - curfew).total_seconds() // 60)
        inside.append({
            "log_id": row["id"],
            "student_id": s_id,
            "name": names[s_id],
            "college": row.get("college") or "-",
            "time_in": format_time(time_in) if time_in else str(row["timestamp"]),
            "overdue": overdue,
            "minutes_over": minutes_over,
        })
    inside.sort(key=lambda v: (not v["overdue"], -v["minutes_over"], v["name"]))

    frequency = sorted(
        ({"student_id": s_id, "name": names.get(s_id, s_id), "count": count} for s_id, count in entries.items()),
        key=lambda v: (-v["count"], v["name"]),
    )

    recent = [
        {
            "id": row["id"],
            "student_id": row["student_id"],
            "name": pretty_name(row.get("normalized_name")),
            "college": row.get("college") or "-",
            "action": row["action"],
            "timestamp": row["timestamp"],
        }
        for row in logs[:300]
    ]

    return jsonify({
        "inside": inside,
        "logs": recent,
        "frequency": frequency,
        "total_entries": sum(entries.values()),
        "curfew_label": "8:00 PM",
    })
