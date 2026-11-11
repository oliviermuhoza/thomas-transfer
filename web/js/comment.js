/* Sends the comment to the server. It is saved in the database and only the admin can read it. */
document.getElementById('comment-form').addEventListener('submit', async function (e) {
  e.preventDefault();
  var form = e.target, msg = document.getElementById('comment-status'), btn = form.querySelector('button');
  msg.className = 'status'; msg.textContent = T('Sending...'); btn.disabled = true;
  try {
    var res = await window.ttFetch('/api/comment', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        name: document.getElementById('m-name').value,
        rating: document.getElementById('m-rate').value,
        text: document.getElementById('m-text').value
      })
    });
    if (!res.ok) throw new Error('failed');
    form.reset();
    msg.className = 'status ok'; msg.textContent = T('Thank you. Your comment was sent.');
  } catch (err) {
    msg.className = 'status bad'; msg.textContent = T('Your comment could not be sent. Please try again.');
  }
  btn.disabled = false;
});
