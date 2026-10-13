HTML_GUARD_STATION = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guard Station Dashboard | GuardGate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: linear-gradient(135deg, #021a0f 0%, #053b22 100%);
            color: #e2e8f0;
        }
        .glass-panel {
            background: rgba(6, 38, 23, 0.65);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(212, 175, 55, 0.2);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        }
        .gold-text { color: #d4af37; }
        .gold-bg { background-color: #d4af37; color: #021a0f; }
        .gold-border { border-color: rgba(212, 175, 55, 0.4); }
        .gold-hover:hover { background-color: #f1c40f; color: #021a0f; }
        .tab-active {
            border-bottom: 2px solid #d4af37;
            color: #d4af37;
            background: rgba(212, 175, 55, 0.1);
        }
        .tab-inactive {
            color: #94a3b8;
            border-bottom: 2px solid transparent;
        }
        .tab-inactive:hover {
            color: #e2e8f0;
            background: rgba(255, 255, 255, 0.05);
        }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 8px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #d4af37; border-radius: 8px; }
    </style>
</head>
<body class="h-screen w-screen overflow-hidden flex flex-col relative">
    <div class="max-w-7xl mx-auto w-full p-4 md:p-6 flex-grow flex flex-col h-full overflow-hidden">
        <!-- Header -->
        <header class="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b gold-border shrink-0">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl gold-bg flex items-center justify-center shadow-[0_0_15px_rgba(212,175,55,0.4)]">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                </div>
                <div>
                    <h1 class="text-2xl font-bold gold-text tracking-wider uppercase">Guard Station</h1>
                    <p class="text-xs text-slate-400 font-medium tracking-wide mt-1">Admin Dashboard & Analytics</p>
                </div>
            </div>
            <div class="flex gap-3">
                <a href="/scanner" class="px-4 py-2 text-xs font-bold uppercase tracking-wider text-[#d4af37] bg-black/40 border gold-border rounded-xl hover:bg-[#d4af37]/10 transition-colors shadow-sm flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                    Scanner Feed
                </a>
                <a href="/logout" class="px-4 py-2 text-xs font-bold uppercase tracking-wider text-rose-400 bg-rose-950/40 border border-rose-500/30 rounded-xl hover:bg-rose-900/60 transition-colors shadow-sm flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                    Logout
                </a>
            </div>
        </header>

        <!-- Stats Overview -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 shrink-0">
            <div class="glass-panel p-5 rounded-2xl border gold-border flex items-center gap-4">
                <div class="p-3 bg-[#d4af37]/10 rounded-xl gold-text"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg></div>
                <div><p class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Total Registered</p><p class="text-2xl font-bold text-white" id="stat-total">0</p></div>
            </div>
            <div class="glass-panel p-5 rounded-2xl border gold-border flex items-center gap-4">
                <div class="p-3 bg-emerald-500/10 rounded-xl text-emerald-400"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg></div>
                <div><p class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Entries Today</p><p class="text-2xl font-bold text-white" id="stat-today">0</p></div>
            </div>
            <div class="glass-panel p-5 rounded-2xl border gold-border flex items-center gap-4">
                <div class="p-3 bg-rose-500/10 rounded-xl text-rose-400"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg></div>
                <div><p class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Unknowns Logged</p><p class="text-2xl font-bold text-white" id="stat-unknowns">0</p></div>
            </div>
            <div class="glass-panel p-5 rounded-2xl border gold-border flex items-center gap-4">
                <div class="p-3 bg-blue-500/10 rounded-xl text-blue-400"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg></div>
                <div><p class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Profiles Synced</p><p class="text-2xl font-bold text-white" id="stat-synced">Yes</p></div>
            </div>
        </div>

        <div class="flex-grow flex flex-col md:flex-row gap-6 h-full overflow-hidden">
            
            <!-- Left Column: Navigation & Tools -->
            <div class="w-full md:w-1/4 flex flex-col gap-4 overflow-y-auto custom-scrollbar pr-2 h-full">
                <!-- Navigation -->
                <div class="glass-panel rounded-2xl overflow-hidden border gold-border">
                    <button onclick="switchTab('logs')" id="btn-logs" class="w-full flex items-center gap-3 px-5 py-4 text-sm font-bold uppercase tracking-wider transition-all tab-active text-left">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                        Access Logs
                    </button>
                    <button onclick="switchTab('database')" id="btn-database" class="w-full flex items-center gap-3 px-5 py-4 text-sm font-bold uppercase tracking-wider transition-all tab-inactive text-left">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path></svg>
                        Profile Directory
                    </button>
                    <button onclick="switchTab('analytics')" id="btn-analytics" class="w-full flex items-center gap-3 px-5 py-4 text-sm font-bold uppercase tracking-wider transition-all tab-inactive text-left">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                        Analytics
                    </button>
                </div>
                
                <!-- Quick Tools -->
                <div class="glass-panel rounded-2xl p-5 border gold-border flex-grow">
                    <h3 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Quick Actions</h3>
                    <div class="space-y-3">
                        <button onclick="exportLogs()" class="w-full py-3 px-4 bg-[#032014] border border-[#d4af37]/30 text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-white/10 transition flex items-center justify-center gap-2">
                            <svg class="w-4 h-4 text-[#d4af37]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                            Export Daily Logs
                        </button>
                        <button onclick="retrainModel()" class="w-full py-3 px-4 bg-[#032014] border border-[#d4af37]/30 text-white rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-white/10 transition flex items-center justify-center gap-2">
                            <svg class="w-4 h-4 text-[#d4af37]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                            Force Re-train Encodings
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Right Column: Content Area -->
            <div class="w-full md:w-3/4 glass-panel rounded-2xl flex flex-col overflow-hidden border gold-border h-full relative">
                
                <!-- Logs Tab -->
                <div id="tab-logs" class="flex flex-col h-full absolute inset-0">
                    <div class="p-5 border-b border-[#d4af37]/20 flex justify-between items-center bg-black/20 shrink-0">
                        <h2 class="font-bold gold-text uppercase tracking-wider flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            Recent Entry Logs
                        </h2>
                        <input type="text" id="log-search" placeholder="Search logs..." class="bg-[#032014] border border-[#d4af37]/30 text-white text-sm rounded-lg px-4 py-2 focus:outline-none focus:border-[#d4af37] w-64 transition placeholder-slate-500">
                    </div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar p-0">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-black/40 text-xs uppercase tracking-wider text-slate-400 sticky top-0 z-10 backdrop-blur-md">
                                <tr>
                                    <th class="px-6 py-4 font-bold border-b border-white/10">Timestamp</th>
                                    <th class="px-6 py-4 font-bold border-b border-white/10">Person</th>
                                    <th class="px-6 py-4 font-bold border-b border-white/10">Type</th>
                                    <th class="px-6 py-4 font-bold border-b border-white/10">Status</th>
                                </tr>
                            </thead>
                            <tbody id="logs-tbody" class="divide-y divide-white/5">
                                <!-- Populated by JS -->
                                <tr><td colspan="4" class="px-6 py-8 text-center text-slate-500">Loading logs...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Database Tab -->
                <div id="tab-database" class="hidden flex flex-col h-full absolute inset-0">
                    <div class="p-5 border-b border-[#d4af37]/20 flex justify-between items-center bg-black/20 shrink-0">
                        <h2 class="font-bold gold-text uppercase tracking-wider flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                            Registered Profiles
                        </h2>
                        <input type="text" id="db-search" placeholder="Search profiles..." class="bg-[#032014] border border-[#d4af37]/30 text-white text-sm rounded-lg px-4 py-2 focus:outline-none focus:border-[#d4af37] w-64 transition placeholder-slate-500">
                    </div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar p-6">
                        <div id="students-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <!-- Populated by JS -->
                            <div class="col-span-full py-8 text-center text-slate-500">Loading profiles...</div>
                        </div>
                    </div>
                </div>

                <!-- Analytics Tab -->
                <div id="tab-analytics" class="hidden flex flex-col h-full absolute inset-0">
                    <div class="p-5 border-b border-[#d4af37]/20 flex justify-between items-center bg-black/20 shrink-0">
                        <h2 class="font-bold gold-text uppercase tracking-wider flex items-center gap-2">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                            Access Trends
                        </h2>
                    </div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar p-6 flex flex-col gap-6">
                        <div class="bg-black/30 p-6 rounded-2xl border border-white/10">
                            <canvas id="logsChart" class="w-full h-64"></canvas>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div class="bg-black/30 p-6 rounded-2xl border border-white/10 flex flex-col">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">By User Type</h3>
                                <div class="flex-grow flex items-center justify-center">
                                    <canvas id="typeChart" class="max-h-48"></canvas>
                                </div>
                            </div>
                            <div class="bg-black/30 p-6 rounded-2xl border border-white/10 flex flex-col">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Peak Hours</h3>
                                <div class="flex-grow flex items-center justify-center text-sm text-slate-500">
                                    Data gathering in progress...
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script>
        const TABS = ['logs', 'database', 'analytics'];
        let chartInstance = null;
        let typeChartInstance = null;

        function switchTab(activeTab) {
            TABS.forEach(tab => {
                const btn = document.getElementById(`btn-${tab}`);
                const content = document.getElementById(`tab-${tab}`);
                if (tab === activeTab) {
                    btn.className = "w-full flex items-center gap-3 px-5 py-4 text-sm font-bold uppercase tracking-wider transition-all tab-active text-left";
                    content.classList.remove('hidden');
                } else {
                    btn.className = "w-full flex items-center gap-3 px-5 py-4 text-sm font-bold uppercase tracking-wider transition-all tab-inactive text-left";
                    content.classList.add('hidden');
                }
            });
            if (activeTab === 'analytics') { setTimeout(initCharts, 100); }
        }

        function initCharts() {
            if (chartInstance) return;
            const ctx = document.getElementById('logsChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['8AM', '10AM', '12PM', '2PM', '4PM', '6PM'],
                    datasets: [{
                        label: 'Entries Today',
                        data: [12, 19, 3, 5, 2, 3],
                        borderColor: '#d4af37',
                        backgroundColor: 'rgba(212, 175, 55, 0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                    }
                }
            });

            const ctxType = document.getElementById('typeChart').getContext('2d');
            typeChartInstance = new Chart(ctxType, {
                type: 'doughnut',
                data: {
                    labels: ['Students', 'Faculty', 'Guests'],
                    datasets: [{
                        data: [65, 20, 15],
                        backgroundColor: ['#d4af37', '#10b981', '#64748b'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { family: "'Plus Jakarta Sans', sans-serif", size: 10, weight: 'bold' } } } }
                }
            });
        }

        function fetchLogs() {
            fetch('/guard/api/logs')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('logs-tbody');
                    tbody.innerHTML = '';
                    if (data.logs.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-8 text-center text-slate-500">No logs for today.</td></tr>';
                        return;
                    }
                    data.logs.forEach(log => {
                        const tr = document.createElement('tr');
                        tr.className = "hover:bg-white/5 transition-colors";
                        
                        // Parse timestamp
                        let timeStr = log.timestamp;
                        if (log.timestamp.includes(' ')) {
                            timeStr = log.timestamp.split(' ')[1];
                        }
                        
                        let statusHtml = '';
                        if (log.status === 'Success') {
                            statusHtml = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Allowed</span>';
                        } else if (log.status === 'Unknown') {
                            statusHtml = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>Flagged</span>';
                        } else {
                            statusHtml = `<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-slate-500/10 text-slate-400 border border-slate-500/20">${log.status}</span>`;
                        }

                        tr.innerHTML = `
                            <td class="px-6 py-4 text-slate-300 font-medium">${timeStr}</td>
                            <td class="px-6 py-4 font-bold text-white">${log.person_name}</td>
                            <td class="px-6 py-4 text-slate-400 text-xs tracking-wider uppercase">${log.person_type}</td>
                            <td class="px-6 py-4">${statusHtml}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                    
                    document.getElementById('stat-today').innerText = data.logs.length;
                    const unknowns = data.logs.filter(l => l.status === 'Unknown').length;
                    document.getElementById('stat-unknowns').innerText = unknowns;
                })
                .catch(() => {});
        }

        function fetchStudents() {
            fetch('/guard/api/students')
                .then(r => r.json())
                .then(data => {
                    const grid = document.getElementById('students-grid');
                    grid.innerHTML = '';
                    if (data.students.length === 0) {
                        grid.innerHTML = '<div class="col-span-full py-8 text-center text-slate-500">Database is empty.</div>';
                        document.getElementById('stat-total').innerText = '0';
                        return;
                    }
                    document.getElementById('stat-total').innerText = data.students.length;
                    data.students.forEach(s => {
                        const card = document.createElement('div');
                        card.className = "bg-black/30 p-5 rounded-2xl border border-white/10 hover:border-[#d4af37]/50 transition-colors shadow-sm flex flex-col gap-3 group";
                        
                        let badgeHtml = '';
                        if (s.user_type === 'Student') {
                            badgeHtml = '<span class="px-2 py-1 rounded bg-[#d4af37]/20 text-[#d4af37] border border-[#d4af37]/30 text-[10px] font-bold uppercase tracking-wider">Student</span>';
                        } else if (s.user_type === 'Faculty') {
                            badgeHtml = '<span class="px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold uppercase tracking-wider">Faculty</span>';
                        } else {
                            badgeHtml = `<span class="px-2 py-1 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] font-bold uppercase tracking-wider">${s.user_type}</span>`;
                        }

                        let details = '';
                        if (s.user_type === 'Student') {
                            details = `<p class="text-xs text-slate-400"><span class="font-semibold text-slate-300">ID:</span> ${s.student_id}</p>
                                       <p class="text-xs text-slate-400 truncate"><span class="font-semibold text-slate-300">Course:</span> ${s.course}</p>`;
                        } else if (s.user_type === 'Faculty') {
                            details = `<p class="text-xs text-slate-400 truncate"><span class="font-semibold text-slate-300">Dept:</span> ${s.department || 'N/A'}</p>`;
                        } else {
                            details = `<p class="text-xs text-slate-400 truncate"><span class="font-semibold text-slate-300">Info:</span> ${s.other_address || s.parent_address || 'N/A'}</p>`;
                        }

                        card.innerHTML = `
                            <div class="flex justify-between items-start">
                                <div>
                                    <h3 class="font-bold text-white text-base">${s.fname} ${s.surname}</h3>
                                    <p class="text-xs text-slate-500 mt-0.5">Registered: ${s.registered_at.split(' ')[0]}</p>
                                </div>
                                ${badgeHtml}
                            </div>
                            <div class="mt-2 pt-3 border-t border-white/5 space-y-1.5">
                                ${details}
                            </div>
                            <button class="mt-2 w-full py-2 bg-white/5 hover:bg-rose-500/20 text-slate-300 hover:text-rose-400 text-[10px] font-bold uppercase tracking-widest rounded-lg transition-colors border border-transparent hover:border-rose-500/30 opacity-0 group-hover:opacity-100">
                                Revoke Access
                            </button>
                        `;
                        grid.appendChild(card);
                    });
                })
                .catch(() => {});
        }

        // Initialize
        fetchLogs();
        fetchStudents();
        setInterval(fetchLogs, 5000); // Poll logs every 5s

        // Client-side search filters
        document.getElementById('log-search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#logs-tbody tr');
            rows.forEach(row => {
                if(row.innerText.toLowerCase().includes(term)) row.style.display = '';
                else row.style.display = 'none';
            });
        });

        document.getElementById('db-search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const cards = document.querySelectorAll('#students-grid > div');
            cards.forEach(card => {
                if(card.innerText.toLowerCase().includes(term)) card.style.display = '';
                else card.style.display = 'none';
            });
        });

        function exportLogs() {
            alert('Exporting logs to CSV... (Demonstration)');
        }
        function retrainModel() {
            alert('Triggering face encodings rebuild... (Demonstration)');
        }
    </script>
</body>
</html>
"""
