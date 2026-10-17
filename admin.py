from flask import Blueprint, render_template_string, request, jsonify, session, redirect, url_for
from supabase import create_client, Client

admin_bp = Blueprint('admin_bp', __name__)

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dormitory Admin Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%); }
    </style>
    <script>
        // Hamburger menu toggle logic
        function toggleNavMenu(event) {
            event.stopPropagation();
            const panel = document.getElementById('nav-menu-panel');
            const open = panel.classList.toggle('hidden') === false;
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', String(open));
        }

        function closeNavMenu() {
            const panel = document.getElementById('nav-menu-panel');
            if (panel) {
                panel.classList.add('hidden');
                document.getElementById('nav-menu-btn').setAttribute('aria-expanded', 'false');
            }
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#nav-menu-panel') && !e.target.closest('#nav-menu-btn')) closeNavMenu();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeNavMenu();
        });
    </script>
</head>
<body class="text-slate-800 p-6 min-h-screen">
    <div class="max-w-6xl mx-auto">
        <!-- HEADER NA MAY HAMBURGER BUTTON -->
        <header class="flex justify-between items-center mb-6 bg-white p-5 rounded-2xl shadow-sm border border-emerald-900/10">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                </div>
                <div>
                    <h1 class="text-xl font-bold text-emerald-950">Dormitory Admin Dashboard</h1>
                    <p class="text-xs text-slate-500">Real-time occupancy and visitor management</p>
                </div>
            </div>

            <!-- HAMBURGER MENU SA ADMIN -->
            <div class="relative shrink-0 flex items-center gap-3">
                <button type="button" id="nav-menu-btn" onclick="toggleNavMenu(event)" aria-haspopup="true" aria-expanded="false" aria-controls="nav-menu-panel" aria-label="Open menu" class="w-10 h-10 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white flex items-center justify-center shadow-sm border border-emerald-900/20 transition focus:outline-none focus:ring-4 focus:ring-emerald-500/20">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                </button>
                <div id="nav-menu-panel" role="menu" class="hidden absolute right-0 top-12 mt-2 w-56 bg-white rounded-xl shadow-xl shadow-slate-900/10 border border-slate-200 py-1.5 z-40">
                    <p class="px-4 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Navigate</p>
                    <a href="/guard" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                        Guard Station
                    </a>
                    <a href="/scanner" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        Student Scanner
                    </a>
                    <div class="my-1.5 border-t border-slate-100"></div>
                    <a href="/admin-logout" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors">
                        <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                        Logout
                    </a>
                </div>
            </div>
        </header>

        <!-- Realtime Chart Section -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-emerald-900/10 mb-6">
            <h2 class="text-sm font-bold text-emerald-950 mb-4 flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse"></span>
                Real-time: Sino ang nasa loob ng Dormitory (Per College)
            </h2>
            <div class="w-full h-64 flex justify-center">
                <canvas id="dormChart"></canvas>
            </div>
        </div>

        <!-- Visitors Management Table -->
        <div class="bg-white p-6 rounded-2xl shadow-sm border border-emerald-900/10">
            <h2 class="text-sm font-bold text-emerald-950 mb-4">Manage Visitors</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="border-b border-slate-100 text-slate-400 uppercase font-semibold">
                            <th class="p-3">ID Number</th>
                            <th class="p-3">Full Name</th>
                            <th class="p-3">Category / College</th>
                            <th class="p-3">Course / Details</th>
                            <th class="p-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="visitors-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let dormChart = null;

        function loadDashboardData() {
            fetch('/api/admin/stats')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('visitors-tbody');
                    tbody.innerHTML = '';
                    if (data.visitors.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400">No visitors found.</td></tr>`;
                        return;
                    }
                    data.visitors.forEach(v => {
                        const safeId = (v.student_id || '').replace(/'/g, "\\'");
                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 hover:bg-emerald-50/30 transition-colors">
                                <td class="p-3 font-semibold text-slate-900">${v.student_id}</td>
                                <td class="p-3 font-medium">${v.normalized_name}</td>
                                <td class="p-3"><span class="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-semibold">${v.college}</span></td>
                                <td class="p-3 text-slate-600">${v.course_year || '-'}</td>
                                <td class="p-3 flex gap-2">
                                    <button onclick="deleteVisitor('${safeId}')" class="bg-rose-50 text-rose-700 border border-rose-200 px-3 py-1 rounded-lg font-medium hover:bg-rose-100 transition">Delete</button>
                                </td>
                            </tr>`;
                    });
                    updateChart(data.inside_count);
                }).catch(() => {});
        }

        function initChart() {
            const ctx = document.getElementById('dormChart').getContext('2d');
            dormChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['CCIS', 'CAS', 'COE', 'CBEA', 'CAFSD', 'CHS', 'COL', 'CASAT', 'CIT', 'CTE', 'Others'],
                    datasets: [{
                        label: 'Aktibong nasa Loob',
                        data: Array(11).fill(0),
                        backgroundColor: '#047857',
                        borderRadius: 6
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        function updateChart(counts) {
            if (!dormChart) return;
            dormChart.data.datasets[0].data = [
                counts.CCIS || 0, counts.CAS || 0, counts.COE || 0, counts.CBEA || 0,
                counts.CAFSD || 0, counts.CHS || 0, counts.COL || 0, counts.CASAT || 0,
                counts.CIT || 0, counts.CTE || 0, counts.Others || 0
            ];
            dormChart.update();
        }

        function deleteVisitor(id) {
            if (!confirm('Sigurado ka bang gusto mong burahin ang visitor na ito?')) return;
            fetch('/api/admin/delete-visitor', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_id: id })
            }).then(r => r.json()).then(res => {
                alert(res.message);
                loadDashboardData();
            });
        }

        window.onload = () => {
            initChart();
            loadDashboardData();
            setInterval(loadDashboardData, 5000);
        };
    </script>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%); }</style>
</head>
<body class="flex items-center justify-center h-screen p-4">
    <div class="bg-white p-8 rounded-2xl shadow-lg w-full max-w-sm border border-emerald-900/10">
        <div class="mx-auto w-12 h-12 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md mb-4">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
        </div>
        <h2 class="text-xl font-bold text-emerald-950 text-center mb-1">Admin Dashboard</h2>
        <p class="text-xs text-slate-500 text-center mb-6">Sign in to manage dormitory records</p>
        {% if error %}<p class="bg-rose-50 border border-rose-200 text-rose-700 text-xs px-3 py-2 rounded-lg mb-4 text-center font-medium">{{ error }}</p>{% endif %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">Username</label>
                <input type="text" name="username" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">Password</label>
                <input type="password" name="password" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
            </div>
            <button type="submit" class="w-full bg-emerald-800 hover:bg-emerald-900 text-white text-sm font-semibold py-2.5 rounded-xl shadow-sm transition">Login</button>
        </form>
    </div>
</body>
</html>
"""

@admin_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    # Kung naka-login na (may active session), diretso agad sa dashboard!
    if session.get('is_admin'):
        return redirect(url_for('admin_bp.admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'mmsu@admin123' and password == 'adminMmsu':
            session['is_admin'] = True
            return redirect(url_for('admin_bp.admin_dashboard'))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error='Invalid credentials')
            
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@admin_bp.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_bp.admin_login'))

@admin_bp.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_bp.admin_login'))
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE)

@admin_bp.route('/api/admin/stats')
def admin_stats():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 401
    
    visitors = supabase.table("visitors").select("*").execute().data or []
    inside_counts = {"CCIS": 0, "CAS": 0, "COE": 0, "CBEA": 0, "CAFSD": 0, "CHS": 0, "COL": 0, "CASAT": 0, "CIT": 0, "CTE": 0, "Others": 0}
    
    for v in visitors:
        s_id = v["student_id"]
        logs = supabase.table("logs").select("action").eq("student_id", s_id).order("id", desc=True).limit(1).execute().data
        if logs and logs[0]["action"] == "Time In":
            col = v.get("college", "Others")
            if col in inside_counts:
                inside_counts[col] += 1
            else:
                inside_counts["Others"] += 1

    return jsonify({"visitors": visitors, "inside_count": inside_counts})

@admin_bp.route('/api/admin/delete-visitor', methods=['POST'])
def admin_delete_visitor():
    if not session.get('is_admin'):
        return jsonify({"message": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    s_id = data.get('student_id')
    if not s_id:
        return jsonify({"message": "Missing student ID"}), 400
        
    try:
        supabase.table("visitors").delete().eq("student_id", s_id).execute()
        supabase.table("logs").delete().eq("student_id", s_id).execute()
        return jsonify({"message": "Visitor successfully deleted!"})
    except Exception as e:
        return jsonify({"message": f"Error: {e}"}), 500