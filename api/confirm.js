// 토스페이먼츠 결제 승인 (서버 전용) — Vercel Serverless Function
// 프론트에서 결제창이 successUrl로 리다이렉트되며 넘긴 {paymentKey, orderId, amount}를
// 받아 서버에서 토스 승인 API로 최종 확정한다. secret 키는 절대 프론트에 두지 않는다.
//
// 필요 환경변수 (Vercel Project Settings > Environment Variables):
//   TOSS_SECRET_KEY = 토스 시크릿 키 (테스트: test_sk_..., 라이브: live_sk_...)
//   이 값은 서버에서만 읽히며 응답/로그에 절대 노출하지 않는다.

// 서버가 인정하는 상품 가격(원). 클라이언트가 보낸 금액을 신뢰하지 않고 이 목록으로 검증한다.
// (금액 위변조 방지 — 결제 보안의 핵심)
const ALLOWED_AMOUNTS = new Set([777]);

const TOSS_CONFIRM_URL = 'https://api.tosspayments.com/v1/payments/confirm';

module.exports = async (req, res) => {
  // POST만 허용
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false, error: 'method_not_allowed' });
  }

  // 본문 파싱 (Vercel이 JSON을 자동 파싱하지만, 문자열로 올 경우도 방어)
  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch { body = null; }
  }
  if (!body || typeof body !== 'object') {
    return res.status(400).json({ ok: false, error: 'invalid_body' });
  }

  const { paymentKey, orderId } = body;
  const amount = Number(body.amount);

  // 필드 검증
  if (typeof paymentKey !== 'string' || paymentKey.length < 1 || paymentKey.length > 200) {
    return res.status(400).json({ ok: false, error: 'invalid_paymentKey' });
  }
  if (typeof orderId !== 'string' || orderId.length < 6 || orderId.length > 64) {
    return res.status(400).json({ ok: false, error: 'invalid_orderId' });
  }
  if (!Number.isInteger(amount) || !ALLOWED_AMOUNTS.has(amount)) {
    // 클라이언트가 임의 금액을 보냈다면 여기서 차단
    return res.status(400).json({ ok: false, error: 'invalid_amount' });
  }

  const secretKey = process.env.TOSS_SECRET_KEY;
  if (!secretKey) {
    // 키 미설정 = 서버 구성 오류. 절대 승인 진행하지 않는다.
    return res.status(500).json({ ok: false, error: 'server_not_configured' });
  }

  // Basic 인증: base64("secretKey:")  — 비밀번호 없이 콜론만
  const auth = 'Basic ' + Buffer.from(secretKey + ':').toString('base64');

  let tossRes, data;
  try {
    tossRes = await fetch(TOSS_CONFIRM_URL, {
      method: 'POST',
      headers: {
        'Authorization': auth,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ paymentKey, orderId, amount })
    });
    data = await tossRes.json();
  } catch (e) {
    return res.status(502).json({ ok: false, error: 'toss_unreachable' });
  }

  if (!tossRes.ok) {
    // 토스가 거부(잔액부족·중복승인·위조 등). code/message만 안전하게 전달.
    return res.status(402).json({
      ok: false,
      error: 'confirm_failed',
      code: (data && data.code) || 'UNKNOWN',
      message: (data && data.message) || '결제 승인에 실패했어요.'
    });
  }

  // 승인 성공 — 서버가 실제 확정된 금액을 다시 한번 검증 (이중 안전장치)
  if (data.status !== 'DONE' || Number(data.totalAmount) !== amount) {
    return res.status(409).json({ ok: false, error: 'amount_mismatch' });
  }

  // 최소한의 결과만 반환 (카드/개인정보 등 민감 필드는 프론트로 넘기지 않는다)
  return res.status(200).json({
    ok: true,
    orderId: data.orderId,
    amount: data.totalAmount,
    approvedAt: data.approvedAt || null
  });
};
