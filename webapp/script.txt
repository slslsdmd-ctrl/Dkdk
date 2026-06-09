const tg = window.Telegram.WebApp;
tg.expand();

const balanceEl = document.getElementById('balance');
const refillBtn = document.getElementById('refillBtn');
const depositModal = document.getElementById('depositModal');
const closeModal = document.getElementById('closeModal');
const copyAddress = document.getElementById('copyAddress');
const walletAddressSpan = document.getElementById('walletAddress');

function deposit(amount) {
    tg.sendData(JSON.stringify({ action: 'deposit', amount: amount }));
    depositModal.style.display = 'none';
}

if(copyAddress) {
    copyAddress.onclick = () => {
        navigator.clipboard.writeText(walletAddressSpan.textContent);
        tg.showPopup({ title: 'Скопировано', message: 'Адрес скопирован!' });
    };
}

if(refillBtn) refillBtn.onclick = () => depositModal.style.display = 'flex';
if(closeModal) closeModal.onclick = () => depositModal.style.display = 'none';
if(depositModal) depositModal.onclick = (e) => { if (e.target === depositModal) depositModal.style.display = 'none'; };

document.querySelectorAll('.amount-btn').forEach(btn => {
    btn.onclick = () => deposit(parseFloat(btn.dataset.amount));
});

const customPayBtn = document.getElementById('customPayBtn');
if(customPayBtn) {
    customPayBtn.onclick = () => {
        const amount = parseFloat(document.getElementById('customAmount').value);
        if (isNaN(amount) || amount < 0.1) {
            tg.showPopup({ title: 'Ошибка', message: 'Введите сумму от 0.1 TON' });
            return;
        }
        deposit(amount);
    };
}

document.querySelectorAll('.game-card').forEach(card => {
    card.onclick = () => {
        tg.sendData(JSON.stringify({ action: 'game', game: card.dataset.game }));
    };
});

window.onload = () => {
    if(balanceEl) balanceEl.textContent = "0";
};