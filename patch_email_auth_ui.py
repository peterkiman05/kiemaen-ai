with open("web/index.html", "r") as f:
    html = f.read()

if "authEmail" in html:
    print("Already patched.")
else:
    old_modal = '''<div class="modal-overlay" id="authModal">
  <div class="modal-box">
    <span class="close-x" onclick="closeAuthModal()">&#10005;</span>
    <h2 id="authTitle">Login</h2>
    <input type="text" id="authUsername" placeholder="Username">
    <input type="password" id="authPassword" placeholder="Password">
    <button class="submit" id="authSubmitBtn" onclick="submitAuth()">Login</button>
    <span class="switch-link" id="authSwitch" onclick="switchAuthMode()">Don't have an account? Register</span>
  </div>
</div>'''

    new_modal = '''<div class="modal-overlay" id="authModal">
  <div class="modal-box">
    <span class="close-x" onclick="closeAuthModal()">&#10005;</span>
    <h2 id="authTitle">Login</h2>
    <input type="text" id="authUsername" placeholder="Username">
    <input type="email" id="authEmail" placeholder="Email" style="display:none;">
    <input type="password" id="authPassword" placeholder="Password">
    <input type="text" id="authCode" placeholder="6-digit verification code" style="display:none;">
    <button class="submit" id="authSubmitBtn" onclick="submitAuth()">Login</button>
    <button class="submit" id="authVerifyBtn" onclick="submitVerifyCode()" style="display:none;">Verify & Create Account</button>
    <span class="switch-link" id="authSwitch" onclick="switchAuthMode()">Don't have an account? Register</span>
  </div>
</div>'''

    html = html.replace(old_modal, new_modal, 1)

    old_js = '''async function submitAuth(){
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;
  if(!username || !password) return;
  const fd = new FormData();
  fd.append('username', username);
  fd.append('password', password);
  const endpoint = authMode === 'login' ? '/login' : '/register';
  const res = await fetch(endpoint, { method:'POST', body: fd });
  const data = await res.json();
  if(data.status === 'ok'){
    token = data.token;
    localStorage.setItem('kiemaen_token', token);
    isAdmin = data.is_admin;
    updateAuthUI(data.username, data.is_admin);
    closeAuthModal();
  } else {
    alert(data.message);
  }
}'''

    new_js = '''let pendingVerifyEmail = null;

async function submitAuth(){
  const username = document.getElementById('authUsername').value.trim();
  const password = document.getElementById('authPassword').value;

  if(authMode === 'login'){
    if(!username || !password) return;
    const fd = new FormData();
    fd.append('username', username);
    fd.append('password', password);
    const res = await fetch('/login', { method:'POST', body: fd });
    const data = await res.json();
    if(data.status === 'ok'){
      token = data.token;
      localStorage.setItem('kiemaen_token', token);
      isAdmin = data.is_admin;
      updateAuthUI(data.username, data.is_admin);
      closeAuthModal();
    } else {
      alert(data.message);
    }
    return;
  }

  // Register mode - phase 1: request the code
  const email = document.getElementById('authEmail').value.trim();
  if(!username || !email || !password){ alert('Please fill in all fields.'); return; }

  const fd = new FormData();
  fd.append('username', username);
  fd.append('email', email);
  fd.append('password', password);
  const res = await fetch('/register/request-code', { method:'POST', body: fd });
  const data = await res.json();
  if(data.status === 'ok'){
    pendingVerifyEmail = email;
    document.getElementById('authUsername').style.display = 'none';
    document.getElementById('authEmail').style.display = 'none';
    document.getElementById('authPassword').style.display = 'none';
    document.getElementById('authSubmitBtn').style.display = 'none';
    document.getElementById('authCode').style.display = 'block';
    document.getElementById('authVerifyBtn').style.display = 'block';
    document.getElementById('authTitle').innerText = 'Check your email';
  } else {
    alert(data.message);
  }
}

async function submitVerifyCode(){
  const code = document.getElementById('authCode').value.trim();
  if(!code || !pendingVerifyEmail) return;
  const fd = new FormData();
  fd.append('email', pendingVerifyEmail);
  fd.append('code', code);
  const res = await fetch('/register/verify', { method:'POST', body: fd });
  const data = await res.json();
  if(data.status === 'ok'){
    token = data.token;
    localStorage.setItem('kiemaen_token', token);
    isAdmin = data.is_admin;
    updateAuthUI(data.username, data.is_admin);
    closeAuthModal();
    resetAuthModal();
  } else {
    alert(data.message);
  }
}

function resetAuthModal(){
  pendingVerifyEmail = null;
  document.getElementById('authUsername').style.display = 'block';
  document.getElementById('authEmail').style.display = authMode === 'register' ? 'block' : 'none';
  document.getElementById('authPassword').style.display = 'block';
  document.getElementById('authCode').style.display = 'none';
  document.getElementById('authSubmitBtn').style.display = 'block';
  document.getElementById('authVerifyBtn').style.display = 'none';
  document.getElementById('authUsername').value = '';
  document.getElementById('authEmail').value = '';
  document.getElementById('authPassword').value = '';
  document.getElementById('authCode').value = '';
}'''

    html = html.replace(old_js, new_js, 1)

    # Update switchAuthMode to toggle email field visibility + reset the two-phase flow
    old_switch = '''function switchAuthMode(){
  authMode = authMode === 'login' ? 'register' : 'login';
  document.getElementById('authTitle').innerText = authMode === 'login' ? 'Login' : 'Register';
  document.getElementById('authSubmitBtn').innerText = authMode === 'login' ? 'Login' : 'Create Account';
  document.getElementById('authSwitch').innerText = authMode === 'login' ? "Don't have an account? Register" : "Already have an account? Login";
}'''

    new_switch = '''function switchAuthMode(){
  authMode = authMode === 'login' ? 'register' : 'login';
  resetAuthModal();
  document.getElementById('authTitle').innerText = authMode === 'login' ? 'Login' : 'Register';
  document.getElementById('authSubmitBtn').innerText = authMode === 'login' ? 'Login' : 'Send Verification Code';
  document.getElementById('authSwitch').innerText = authMode === 'login' ? "Don't have an account? Register" : "Already have an account? Login";
}'''

    html = html.replace(old_switch, new_switch, 1)

    with open("web/index.html", "w") as f:
        f.write(html)
    print("Patched web/index.html with email verification UI flow.")
