# VPN para ouvintes — RADIO NO GRALE

O app precisa de uma **rede virtual privada** entre o PC da rádio e os amigos. O Radmin não tem app oficial estável no celular; use uma destas opções (ambas têm app **oficial** no Windows e no Android).

## Recomendado: ZeroTier

- Site: https://www.zerotier.com/
- Apps oficiais: Windows, macOS, Linux, **Android** (Play Store), **iOS**
- Grátis para redes pequenas (até 25 dispositivos no plano free)

### Você (operador)

1. Crie conta em https://my.zerotier.com/
2. **Create A Network** → anote o **Network ID** (16 caracteres). Exemplo deste projeto: `8d1c312afa4fb9e8` — link de convite: https://joinzt.com/addnetwork?nwid=8d1c312afa4fb9e8&v=1
3. No painel, marque **Private** e anote a rede.
4. Instale **ZeroTier One** no PC da rádio: https://www.zerotier.com/download/
5. Entre na rede: ícone da bandeja → **Join Network** → cole o Network ID.
6. No site my.zerotier.com, na rede → **Members** → marque **Auth?** no seu PC (e depois nos amigos quando entrarem).
7. Anote o **IP ZeroTier do seu PC** (Managed IP, ex. `10.6.219.56`) — é esse IP que vai no app da rádio.
8. Opcional (builds zip/APK já com IP): grave em `data/operator-vpn-host.txt` (uma linha, só o IP) e rode `.\scripts\package-app-release.ps1`.
9. Ligue a stack: `.\scripts\start-full-stack.ps1`
10. Firewall: `.\scripts\open-lan-firewall.ps1` (Admin)

### Amigos (PC ou celular)

1. Instalam **ZeroTier One** (mesma loja/site).
2. **Join Network** com o **mesmo Network ID**.
3. Você autoriza o dispositivo deles em **Members** (Auth? ✓).
4. Instalam o app **RadioPoggers** (zip ou APK).
5. No app: **Rede privada (VPN)** → colam o **IP do operador** (seu IP ZeroTier).
6. **Rádio → PLAY**.

---

## Alternativa: Tailscale

- Site: https://tailscale.com/
- Apps oficiais em todas as plataformas (inclui Android e iOS)
- Mais fácil para quem já usa conta Google/Microsoft; IPs tipo `100.x.y.z`

### Você (operador)

1. Conta em https://login.tailscale.com/
2. Instale Tailscale no PC da rádio.
3. Em outro dispositivo ou no admin: veja o IP Tailscale do PC (ex. `100.64.0.5`).
4. Opcional: **Share** da máquina ou convide amigos na mesma “tailnet” (conta/e-mail).

### Amigos

1. Instalam Tailscale, entram na mesma tailnet (convite seu).
2. No RadioPoggers: **Rede privada (VPN)** → IP Tailscale **do PC da rádio**.
3. **Rádio → PLAY**.

---

## O que não muda no app

| Item | Valor |
| --- | --- |
| IP no app | Sempre o IP **do PC do operador na VPN** (não o IP do celular do amigo) |
| API | `http://IP:8765` |
| Stream | `http://IP/listen/radio-no-grale/radio.mp3` |
| Portas no PC da rádio | **8765** (API), **80** (AzuraCast/stream) |

O preset **Rede privada (VPN)** no app monta essas URLs automaticamente a partir do IP que você passar.

---

## Comparativo rápido

| | ZeroTier | Tailscale |
| --- | --- | --- |
| App oficial Android | Sim (Play Store) | Sim (Play Store) |
| App oficial Windows | Sim | Sim |
| Convite | Network ID + você autoriza | E-mail / convite tailnet |
| IP típico | `10.147.x.x` | `100.x.x.x` |
| Conta obrigatória | Sim (grátis) | Sim (grátis) |

---

## IP mudou?

VPN pode trocar o IP do PC após reinício. Confira no app ZeroTier/Tailscale e avise o grupo; todos reaplicam **Mais → Rede privada (VPN)**.

---

## Atualizar o app

Releases pelo zip/APK ou GitHub — **não** precisa de VPN para baixar update; só para **ouvir** a rádio.

Veja também: `docs/APP_OUVINTE.md`, `docs/APP_RELEASE.md`.
