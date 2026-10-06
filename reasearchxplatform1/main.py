from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3, hashlib, json, time, os, re, urllib.request, urllib.error
from pathlib import Path

BASE=Path(__file__).parent
DB=BASE/'researchx.db'
app=FastAPI(title='ResearchX')

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE,phone TEXT,password TEXT NOT NULL,role TEXT NOT NULL,company_name TEXT DEFAULT '',skills TEXT DEFAULT '',age INTEGER DEFAULT 18,created_at INTEGER);
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT NOT NULL,category TEXT,summary TEXT,confidential_brief TEXT,engagement TEXT,budget REAL,required_skills TEXT,status TEXT,owner_id TEXT,created_at INTEGER,updated_at INTEGER,charter_version INTEGER DEFAULT 1,charter_scope TEXT DEFAULT '',rewards_terms TEXT DEFAULT '',roles_eligibility TEXT DEFAULT '',ip_terms TEXT DEFAULT '',confidentiality_terms TEXT DEFAULT '',credit_split TEXT DEFAULT '',exit_dispute_terms TEXT DEFAULT '',commercialization_clause TEXT DEFAULT '',age_minimum INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY,project_id TEXT,student_id TEXT,note TEXT,status TEXT,expected_pay_ack INTEGER DEFAULT 0,charter_version INTEGER DEFAULT 1,guardian_consent INTEGER DEFAULT 0,created_at INTEGER,UNIQUE(project_id,student_id));
CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,user_id TEXT,title TEXT,message TEXT,kind TEXT,project_id TEXT,read INTEGER DEFAULT 0,created_at INTEGER);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,action TEXT,project_id TEXT,payload TEXT,prev_hash TEXT,hash TEXT,created_at INTEGER);
'''

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def hid(s): return hashlib.sha256(s.encode()).hexdigest()
def now(): return int(time.time())
def uid(prefix): return f'{prefix}_{hid(str(time.time_ns()))[:12]}'
def add_ledger(c,actor,action,project_id,payload):
    prev=c.execute('SELECT hash FROM ledger ORDER BY id DESC LIMIT 1').fetchone(); prev=prev['hash'] if prev else 'GENESIS'
    ts=now(); raw=f'{prev}|{actor}|{action}|{project_id}|{json.dumps(payload,sort_keys=True)}|{ts}'; h=hid(raw)
    c.execute('INSERT INTO ledger(actor,action,project_id,payload,prev_hash,hash,created_at) VALUES(?,?,?,?,?,?,?)',(actor,action,project_id,json.dumps(payload),prev,h,ts))

def seed(c):
    if c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']: return
    users=[
      ('usr_student','Maya Sharma','maya@researchx.demo','+919900000001','student123','Student','','Python, AI, Data Science',20),
      ('usr_sponsor','Sunrise Corp.','sponsor@researchx.demo','+919900000002','sponsor123','Sponsor','Sunrise Corp.','AI, Healthcare, Computer Vision',35),
      ('usr_mentor','Dr. Priya Sharma','mentor@researchx.demo','+919900000003','mentor123','Mentor','','AI, Machine Learning, Research',32),
      ('usr_admin','ResearchX Admin','admin@researchx.demo','+919900000004','admin123','Admin','','Governance, Security',30),
    ]
    for u in users:c.execute('INSERT INTO users(id,name,email,phone,password,role,company_name,skills,age,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(u[0],u[1],u[2],u[3],u[4],u[5],u[6],u[7],u[8],now()))
    projects=[
      ('p_retina','Diabetic Retinopathy Detection','Healthcare','Build an AI-assisted screening workflow for retinal images.','Confidential datasets are shared only after accepted charter.','Funded',100000,'Python, AI, Computer Vision','Active','usr_sponsor'),
      ('p_crop','Crop Disease Detection','Agriculture','Detect common crop diseases from field images.','Partner dataset and evaluation protocol.','Funded',80000,'Computer Vision, Python','Active','usr_sponsor'),
      ('p_wind','Wind Energy Forecasting','Clean Energy','Forecast short-horizon wind energy generation.','Internal turbine data.','Funded',150000,'Data Science, Forecasting, Python','Active','usr_sponsor'),
    ]
    for p in projects:
      paid=p[5] in ('Funded','Stipend / honorarium')
      charter=(p[3], 'Budget and milestone schedule stated before work.' if paid else 'No payment; certificates, badges, co-authorship, mentorship or academic credit only.', 'Roles, eligibility and time commitment agreed before work.', 'Ownership, licence, authorship and publication terms agreed before work.', 'Confidential data only for accepted members; approved AI tools only.', 'Credit follows agreed roles and reviewed impact; AI does not receive credit.', 'Leaving midway preserves credit for accepted work; disputes use ledger evidence and mediation.', 'If unpaid work is later commercialised, the charter commercialisation clause applies.', 18 if paid else 0)
      c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(p[0],p[1],p[2],p[3],p[4],p[5],p[6],p[7],p[8],p[9],now(),now(),1,*charter))
    for p in projects:add_ledger(c,'usr_sponsor','PROJECT_SEEDED',p[0],{'title':p[1]})
    c.commit()

def migrate():
    c=db()
    existing={r['name'] for r in c.execute("PRAGMA table_info(users)").fetchall()}
    if 'age' not in existing: c.execute("ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 18")
    existing={r['name'] for r in c.execute("PRAGMA table_info(projects)").fetchall()}
    additions={
      'charter_version':'INTEGER DEFAULT 1','charter_scope':"TEXT DEFAULT ''",'rewards_terms':"TEXT DEFAULT ''",
      'roles_eligibility':"TEXT DEFAULT ''",'ip_terms':"TEXT DEFAULT ''",'confidentiality_terms':"TEXT DEFAULT ''",
      'credit_split':"TEXT DEFAULT ''",'exit_dispute_terms':"TEXT DEFAULT ''",'commercialization_clause':"TEXT DEFAULT ''",'age_minimum':'INTEGER DEFAULT 0'
    }
    for name,ddl in additions.items():
        if name not in existing: c.execute(f"ALTER TABLE projects ADD COLUMN {name} {ddl}")
    existing={r['name'] for r in c.execute("PRAGMA table_info(applications)").fetchall()}
    for name,ddl in {'expected_pay_ack':'INTEGER DEFAULT 0','charter_version':'INTEGER DEFAULT 1','guardian_consent':'INTEGER DEFAULT 0'}.items():
        if name not in existing: c.execute(f"ALTER TABLE applications ADD COLUMN {name} {ddl}")
    c.execute("UPDATE users SET age=20 WHERE id='usr_student' AND age=18")
    c.execute("UPDATE users SET age=35 WHERE id='usr_sponsor' AND age=18")
    c.execute("UPDATE users SET age=32 WHERE id='usr_mentor' AND age=18")
    c.execute("UPDATE users SET age=30 WHERE id='usr_admin' AND age=18")
    c.execute("UPDATE projects SET charter_scope=CASE WHEN charter_scope IS NULL OR charter_scope='' THEN summary ELSE charter_scope END, rewards_terms=CASE WHEN rewards_terms IS NULL OR rewards_terms='' THEN CASE WHEN engagement IN ('Funded','Stipend / honorarium') THEN 'Budget and milestone schedule stated before work.' ELSE 'No payment; certificates, badges, co-authorship, mentorship, recommendation or academic credit only.' END ELSE rewards_terms END, roles_eligibility=CASE WHEN roles_eligibility IS NULL OR roles_eligibility='' THEN 'Roles, eligibility and time commitment agreed before work.' ELSE roles_eligibility END, ip_terms=CASE WHEN ip_terms IS NULL OR ip_terms='' THEN 'Ownership, licence, authorship and publication terms agreed before work.' ELSE ip_terms END, confidentiality_terms=CASE WHEN confidentiality_terms IS NULL OR confidentiality_terms='' THEN 'Confidential data is shared only with accepted members; approved AI tools only.' ELSE confidentiality_terms END, credit_split=CASE WHEN credit_split IS NULL OR credit_split='' THEN 'Credit follows agreed roles and reviewed impact; AI does not receive credit.' ELSE credit_split END, exit_dispute_terms=CASE WHEN exit_dispute_terms IS NULL OR exit_dispute_terms='' THEN 'Leaving midway preserves credit for accepted work; disputes use ledger evidence and mediation.' ELSE exit_dispute_terms END, commercialization_clause=CASE WHEN commercialization_clause IS NULL OR commercialization_clause='' THEN 'If unpaid work is later commercialised, the agreed contributor terms in this charter apply.' ELSE commercialization_clause END, age_minimum=CASE WHEN engagement IN ('Funded','Stipend / honorarium') THEN 18 ELSE 0 END")
    c.commit(); c.close()

def init():
    c=db(); c.executescript(SCHEMA); c.commit(); c.close(); migrate(); c=db(); seed(c); c.commit(); c.close()
init()

def user_row(uid):
    c=db(); r=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); c.close(); return r

def auth(uid):
    r=user_row(uid)
    if not r: raise HTTPException(401,'Session expired. Please log in again.')
    return r

def public_user(r):
    return {'id':r['id'],'name':r['name'],'email':r['email'],'phone':r['phone'],'role':r['role'],'company_name':r['company_name'],'skills':r['skills'],'age':r['age']}

def project_obj(c,r):
    owner=c.execute('SELECT * FROM users WHERE id=?',(r['owner_id'],)).fetchone()
    apps=c.execute('SELECT COUNT(*) n FROM applications WHERE project_id=?',(r['id'],)).fetchone()['n']
    return {'id':r['id'],'title':r['title'],'category':r['category'],'public_summary':r['summary'],'confidential_brief':r['confidential_brief'],'engagement_model':r['engagement'],'budget':r['budget'],'required_skills':r['required_skills'],'status':r['status'],'owner_id':r['owner_id'],'sponsor':owner['company_name'] or owner['name'],'sponsor_name':owner['name'],'application_count':apps,'created_at':r['created_at'],'charter_version':r['charter_version'],'charter':{'scope':r['charter_scope'],'rewards_terms':r['rewards_terms'],'roles_eligibility':r['roles_eligibility'],'ip_terms':r['ip_terms'],'confidentiality_terms':r['confidentiality_terms'],'credit_split':r['credit_split'],'exit_dispute_terms':r['exit_dispute_terms'],'commercialization_clause':r['commercialization_clause'],'age_minimum':r['age_minimum']}}

class Login(BaseModel): identifier:str; password:str
class Register(BaseModel): name:str; email:str=''; phone:str=''; password:str; role:str='Student'; company_name:str=''; skills:str=''; age:int=18
class ProjectIn(BaseModel): title:str; category:str='General'; public_summary:str=''; confidential_brief:str=''; engagement_model:str='Funded'; escrow_amount:float=0; required_skills:str=''; status:str='Active'; charter_scope:str=''; rewards_terms:str=''; roles_eligibility:str=''; ip_terms:str=''; confidentiality_terms:str=''; credit_split:str=''; exit_dispute_terms:str=''; commercialization_clause:str=''; age_minimum:int=0
class ProfileIn(BaseModel): company_name:str=''; skills:str=''
class ApplyIn(BaseModel): cover_note:str=''; expected_pay_ack:bool=False; charter_version:int=1; guardian_consent:bool=False
class AIIn(BaseModel): prompt:str

@app.get('/')
def index(): return FileResponse(BASE/'static/index.html')
@app.get('/app.js')
def js(): return FileResponse(BASE/'static/app.js',media_type='application/javascript')
@app.get('/styles.css')
def css(): return FileResponse(BASE/'static/styles.css',media_type='text/css')

@app.post('/auth/login')
def login(x:Login):
    c=db(); r=c.execute('SELECT * FROM users WHERE (lower(email)=lower(?) OR phone=?) AND password=?',(x.identifier,x.identifier,x.password)).fetchone(); c.close()
    if not r: raise HTTPException(401,'Invalid email/phone or password.')
    return {'user':public_user(r)}

@app.post('/auth/register')
def register(x:Register):
    if x.role not in ('Student','Mentor','Sponsor'): raise HTTPException(400,'Invalid role.')
    if x.age < 1 or x.age > 120: raise HTTPException(400,'Enter a valid age.')
    c=db();
    try:
      if x.email and c.execute('SELECT 1 FROM users WHERE email=?',(x.email,)).fetchone(): raise HTTPException(409,'Email already registered.')
      id=uid('usr'); c.execute('INSERT INTO users(id,name,email,phone,password,role,company_name,skills,age,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,x.name,x.email or None,x.phone,x.password,x.role,x.company_name if x.role=='Sponsor' else '',x.skills,x.age,now())); add_ledger(c,id,'USER_REGISTERED','',{'role':x.role}); c.commit(); r=c.execute('SELECT * FROM users WHERE id=?',(id,)).fetchone(); return {'user':public_user(r)}
    finally:c.close()

@app.post('/auth/github')
def github():
    c=db(); r=c.execute("SELECT * FROM users WHERE email='github@researchx.demo'").fetchone()
    if not r:
      id='usr_github_demo'; c.execute('INSERT INTO users(id,name,email,phone,password,role,company_name,skills,age,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,'GitHub Demo User','github@researchx.demo','', 'github-demo','Student','','Software, AI',20,now())); c.commit(); r=c.execute('SELECT * FROM users WHERE id=?',(id,)).fetchone()
    c.close(); return {'user':public_user(r)}

@app.get('/api/state')
def state(x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id); c=db(); ps=c.execute('SELECT * FROM projects ORDER BY created_at DESC').fetchall(); apps=c.execute('SELECT * FROM applications ORDER BY created_at DESC').fetchall(); ledger=c.execute('SELECT * FROM ledger ORDER BY id').fetchall(); c.close()
    return {'user':public_user(u),'projects':[project_obj(db(),p) for p in ps], 'applications':[dict(a) for a in apps], 'ledger':[dict(e) for e in ledger], 'ledgerStatus':{'entries':len(ledger),'valid':verify_ledger(),'root':ledger[-1]['hash'] if ledger else ''}}

def verify_ledger():
    c=db(); rows=c.execute('SELECT * FROM ledger ORDER BY id').fetchall(); prev='GENESIS'
    for r in rows:
      raw=f"{prev}|{r['actor']}|{r['action']}|{r['project_id']}|{r['payload']}|{r['created_at']}"
      if hid(raw)!=r['hash'] or r['prev_hash']!=prev:c.close(); return False
      prev=r['hash']
    c.close(); return True

@app.get('/api/notifications')
def notifications(x_user_id:str=Header(...,alias='X-User-ID')):
    auth(x_user_id); c=db(); rows=c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(x_user_id,)).fetchall(); unread=c.execute('SELECT COUNT(*) n FROM notifications WHERE user_id=? AND read=0',(x_user_id,)).fetchone()['n']; c.close(); return {'items':[dict(r) for r in rows],'unread':unread}
@app.post('/api/notifications/read')
def read_notifications(x_user_id:str=Header(...,alias='X-User-ID')):
    auth(x_user_id); c=db(); c.execute('UPDATE notifications SET read=1 WHERE user_id=?',(x_user_id,)); c.commit(); c.close(); return {'ok':True}

def notify(c,user_id,title,message,kind,project_id): c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?)',(uid('ntf'),user_id,title,message,kind,project_id,0,now()))

def can_edit(u,p): return u['role']=='Admin' or (u['role']=='Sponsor' and p['owner_id']==u['id'])

def create_project(c,u,x,owner_id=None):
    owner_id=owner_id or u['id']; owner=c.execute('SELECT * FROM users WHERE id=?',(owner_id,)).fetchone()
    if not owner or owner['role'] not in ('Sponsor','Admin'): raise HTTPException(400,'Project owner must be a sponsor.')
    pid=uid('prj'); paid=x.engagement_model in ('Funded','Stipend / honorarium')
    age_min=18 if paid else 0
    c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,x.title,x.category,x.public_summary,x.confidential_brief,x.engagement_model,x.escrow_amount,x.required_skills,x.status,owner_id,now(),now(),1,x.charter_scope or x.public_summary,x.rewards_terms or ('Budget and milestone schedule stated before work.' if paid else 'No payment; recognition/credit only.'),x.roles_eligibility or 'Roles, eligibility and time commitment agreed before work.',x.ip_terms or 'Ownership, licence, authorship and publication terms agreed before work.',x.confidentiality_terms or 'Confidential data is shared only with accepted members; approved AI tools only.',x.credit_split or 'Credit follows agreed roles and reviewed impact; AI does not receive credit.',x.exit_dispute_terms or 'Leaving midway preserves credit for accepted work; disputes use ledger evidence and mediation.',x.commercialization_clause or 'If unpaid work is later commercialised, the charter commercialisation clause applies.',age_min))
    add_ledger(c,u['id'],'PROJECT_CREATED',pid,{'title':x.title,'owner_id':owner_id})
    # Notify students by interest match, all admins, and owner if created by admin.
    students=c.execute("SELECT * FROM users WHERE role='Student'").fetchall()
    terms=(x.title+' '+x.category+' '+x.required_skills).lower()
    for s in students:
      skills=s['skills'].lower();
      if not skills or any(t.strip() and t.strip().lower() in terms for t in skills.split(',')):
        notify(c,s['id'],'New project match',f'{owner["company_name"] or owner["name"]} listed “{x.title}” — it may match your skills.', 'project',pid)
    for a in c.execute("SELECT id FROM users WHERE role='Admin'").fetchall(): notify(c,a['id'],'New project listed',f'{owner["company_name"] or owner["name"]} listed “{x.title}”.','project',pid)
    return pid

@app.post('/projects')
def create(x:ProjectIn,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role'] not in ('Sponsor','Admin'): raise HTTPException(403,'Only sponsors or admins can list projects.')
    c=db(); pid=create_project(c,u,x); c.commit(); c.close(); return {'project_id':pid}

@app.get('/admin/projects')
def admin_projects(x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Admin': raise HTTPException(403,'Admin access required.')
    c=db(); rows=c.execute('SELECT * FROM projects ORDER BY created_at DESC').fetchall(); out=[project_obj(c,r) for r in rows]; c.close(); return {'projects':out}

def update_project(pid,x,u):
    c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not p: c.close(); raise HTTPException(404,'Project not found.')
    if not can_edit(u,p): c.close(); raise HTTPException(403,'You cannot edit this project.')
    owner_id=p['owner_id']
    if u['role']=='Admin': owner_id=p['owner_id']
    old_version=p['charter_version'] or 1
    paid=x.engagement_model in ('Funded','Stipend / honorarium')
    new_version=old_version+1
    c.execute('UPDATE projects SET title=?,category=?,summary=?,confidential_brief=?,engagement=?,budget=?,required_skills=?,status=?,owner_id=?,updated_at=?,charter_version=?,charter_scope=?,rewards_terms=?,roles_eligibility=?,ip_terms=?,confidentiality_terms=?,credit_split=?,exit_dispute_terms=?,commercialization_clause=?,age_minimum=? WHERE id=?',(x.title,x.category,x.public_summary,x.confidential_brief,x.engagement_model,x.escrow_amount,x.required_skills,x.status,owner_id,now(),new_version,x.charter_scope or x.public_summary,x.rewards_terms or ('Budget and milestone schedule stated before work.' if paid else 'No payment; recognition/credit only.'),x.roles_eligibility or 'Roles, eligibility and time commitment agreed before work.',x.ip_terms or 'Ownership, licence, authorship and publication terms agreed before work.',x.confidentiality_terms or 'Confidential data is shared only with accepted members; approved AI tools only.',x.credit_split or 'Credit follows agreed roles and reviewed impact; AI does not receive credit.',x.exit_dispute_terms or 'Leaving midway preserves credit for accepted work; disputes use ledger evidence and mediation.',x.commercialization_clause or 'If unpaid work is later commercialised, the charter commercialisation clause applies.',18 if paid else 0,pid))
    add_ledger(c,u['id'],'CHARTER_VERSIONED',pid,{'title':x.title,'status':x.status,'from_version':old_version,'to_version':new_version,'engagement_model':x.engagement_model});
    members=c.execute("SELECT a.*,u.id user_id,u.name FROM applications a JOIN users u ON u.id=a.student_id WHERE a.project_id=? AND a.status NOT LIKE 'Left%'",(pid,)).fetchall()
    for m in members:
      c.execute("UPDATE applications SET status='Reaccept required' WHERE id=?",(m['id'],)); notify(c,m['user_id'],'Project charter changed',f'“{x.title}” moved to Charter v{new_version}. Re-accept the new terms before continuing.', 'charter', pid)
    c.commit(); c.close()

@app.put('/projects/{pid}')
def update(pid:str,x:ProjectIn,x_user_id:str=Header(...,alias='X-User-ID')): update_project(pid,x,auth(x_user_id)); return {'ok':True}
@app.put('/admin/projects/{pid}')
def admin_update(pid:str,x:ProjectIn,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Admin': raise HTTPException(403,'Admin access required.')
    update_project(pid,x,u); return {'ok':True}

def archive(pid,u):
    c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not p: c.close(); raise HTTPException(404,'Project not found.')
    if not can_edit(u,p): c.close(); raise HTTPException(403,'You cannot delete this project.')
    c.execute("UPDATE projects SET status='Archived',updated_at=? WHERE id=?",(now(),pid)); add_ledger(c,u['id'],'PROJECT_ARCHIVED',pid,{}); c.commit(); c.close()
@app.delete('/projects/{pid}')
def delete(pid:str,x_user_id:str=Header(...,alias='X-User-ID')): archive(pid,auth(x_user_id)); return {'ok':True}
@app.delete('/admin/projects/{pid}')
def admin_delete(pid:str,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Admin': raise HTTPException(403,'Admin access required.')
    archive(pid,u); return {'ok':True}

@app.post('/projects/{pid}/apply')
def apply(pid:str,x:ApplyIn,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Student': raise HTTPException(403,'Only students can apply.')
    c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not p or p['status']!='Active': c.close(); raise HTTPException(404,'Project is not accepting applications.')
    if c.execute('SELECT 1 FROM applications WHERE project_id=? AND student_id=?',(pid,u['id'])).fetchone(): c.close(); raise HTTPException(409,'You already applied.')
    if p['age_minimum'] >= 18 and (u['age'] or 0) < 18:
      c.close(); raise HTTPException(403,'Paid work on this project is restricted to participants aged 18 or older.')
    if x.charter_version != p['charter_version']:
      c.close(); raise HTTPException(409,'This project charter has changed. Refresh and accept the latest charter before applying.')
    unpaid=p['engagement'] not in ('Funded','Stipend / honorarium')
    if unpaid and not x.expected_pay_ack:
      c.close(); raise HTTPException(400,'This project is unpaid. You must acknowledge the engagement model before joining.')
    aid=uid('app'); c.execute('INSERT INTO applications(id,project_id,student_id,note,status,expected_pay_ack,charter_version,guardian_consent,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(aid,pid,u['id'],x.cover_note,'Applied',int(x.expected_pay_ack),p['charter_version'],int(x.guardian_consent),now())); owner=c.execute('SELECT * FROM users WHERE id=?',(p['owner_id'],)).fetchone(); notify(c,owner['id'],'New project application',f'{u["name"]} applied to “{p["title"]}”.','application',pid); add_ledger(c,u['id'],'APPLICATION_CREATED',pid,{'application_id':aid}); c.commit(); c.close(); return {'application_id':aid}

@app.get('/projects/{pid}/applications')
def applications(pid:str,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id); c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not p or not can_edit(u,p): c.close(); raise HTTPException(403,'Access denied.')
    rows=c.execute('SELECT a.*,u.name,u.email,u.skills FROM applications a JOIN users u ON u.id=a.student_id WHERE a.project_id=? ORDER BY a.created_at DESC',(pid,)).fetchall(); c.close(); return {'applications':[dict(r) for r in rows]}

@app.post('/projects/{pid}/reaccept')
def reaccept(pid:str,x:ApplyIn,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Student': raise HTTPException(403,'Only students can re-accept a charter.')
    c=db(); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone(); a=c.execute('SELECT * FROM applications WHERE project_id=? AND student_id=?',(pid,u['id'])).fetchone()
    if not p or not a: c.close(); raise HTTPException(404,'Project or membership not found.')
    if p['age_minimum']>=18 and (u['age'] or 0)<18: c.close(); raise HTTPException(403,'Paid work requires participants to be 18 or older.')
    if x.charter_version!=p['charter_version']: c.close(); raise HTTPException(409,'Please refresh for the latest charter version.')
    unpaid=p['engagement'] not in ('Funded','Stipend / honorarium')
    if unpaid and not x.expected_pay_ack: c.close(); raise HTTPException(400,'Please acknowledge that this project is unpaid.')
    c.execute('UPDATE applications SET status=?,expected_pay_ack=?,charter_version=? WHERE id=?',('Reaccepted',int(x.expected_pay_ack),p['charter_version'],a['id']))
    add_ledger(c,u['id'],'CHARTER_REACCEPTED',pid,{'application_id':a['id'],'version':p['charter_version']}); c.commit(); c.close(); return {'ok':True}

@app.post('/projects/{pid}/leave')
def leave_project(pid:str,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id)
    if u['role']!='Student': raise HTTPException(403,'Only students can leave as a participant.')
    c=db(); a=c.execute('SELECT * FROM applications WHERE project_id=? AND student_id=?',(pid,u['id'])).fetchone()
    if not a: c.close(); raise HTTPException(404,'Participation not found.')
    c.execute("UPDATE applications SET status='Left — credit preserved' WHERE id=?",(a['id'],)); add_ledger(c,u['id'],'PROJECT_LEFT_CREDIT_PRESERVED',pid,{'application_id':a['id']}); p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone(); owner=c.execute('SELECT * FROM users WHERE id=?',(p['owner_id'],)).fetchone(); notify(c,owner['id'],'Participant left','A participant left after accepted work; contribution credit is preserved in the ledger.','application',pid); c.commit(); c.close(); return {'ok':True}

@app.put('/profile')
def profile(x:ProfileIn,x_user_id:str=Header(...,alias='X-User-ID')):
    u=auth(x_user_id); company=x.company_name if u['role']=='Sponsor' else u['company_name']; c=db(); c.execute('UPDATE users SET company_name=?,skills=? WHERE id=?',(company,x.skills,u['id'])); c.commit(); r=c.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone(); c.close(); return {'user':public_user(r)}

@app.post('/ledger/verify')
def ledger_verify(x_user_id:str=Header(...,alias='X-User-ID')): auth(x_user_id); return {'valid':verify_ledger()}

def ollama_answer(prompt):
    # Uses a local Ollama server when available; no cloud/API key required.
    base=os.getenv('OLLAMA_HOST','http://127.0.0.1:11434').rstrip('/')
    model=os.getenv('OLLAMA_MODEL','').strip()
    try:
        if not model:
            req=urllib.request.Request(base+'/api/tags',headers={'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as r:
                tags=json.loads(r.read().decode('utf-8'))
            models=tags.get('models') or []
            if not models: return None
            model=models[0].get('name') or models[0].get('model')
        if not model: return None
        payload=json.dumps({
            'model':model,
            'prompt':('You are ResearchX local AI assistant. Give practical, concise help for research collaboration, project scoping, milestones, coding, matching, rewards and security. Never claim AI itself owns credit. Do not request or expose confidential project data.\n\nUser request: '+prompt),
            'stream':False,
            'options':{'temperature':0.2}
        }).encode('utf-8')
        req=urllib.request.Request(base+'/api/generate',data=payload,headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=30) as r:
            out=json.loads(r.read().decode('utf-8'))
        ans=(out.get('response') or '').strip()
        return ans or None
    except Exception:
        return None

@app.post('/api/ai')
def ai(x:AIIn,x_user_id:str=Header(...,alias='X-User-ID')):
    auth(x_user_id); q=x.prompt.lower()
    # First try the local Ollama model. If Ollama is unavailable, keep the built-in
    # demo assistant so the hackathon app never breaks.
    live=ollama_answer(x.prompt)
    if live: return {'answer':live,'provider':'ollama'}
    if any(w in q for w in ('milestone','scope','project')): ans='Start with measurable milestones: (1) define dataset/input, (2) build baseline, (3) validate against agreed metrics, (4) sponsor review, (5) release reward. Keep confidential data outside the AI prompt unless the approved secure model is used.'
    elif any(w in q for w in ('code','python','api','javascript')): ans='For coding, describe the exact input, output, framework and error. A good request is: “Write a FastAPI endpoint that accepts a project_id and returns matched students with a score and explanation.” I can then propose the implementation.'
    elif 'reward' in q or 'split' in q: ans='A simple demo split is 85% contributor pool, 10% mentor pool and 5% platform fee. Make the split visible in the project charter before work starts.'
    elif 'leak' in q or 'security' in q: ans='Use role-based access, keep confidential briefs behind project membership, redact PII before external AI calls, and use the hash-chained ledger for tamper evidence. A ledger prevents silent history changes; it does not by itself prevent data leakage.'
    else: ans='I can help scope a project, generate milestones, design APIs, debug code, suggest matching criteria, or explain ResearchX security and reward logic. Tell me the concrete task and your current inputs.'
    return {'answer':ans,'provider':'fallback'}

app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
