# GitHub yayın kontrol listesi

Bu liste FlowDesk'i herkese açık depoya gönderirken gizli veya yerel dosyaların
yanlışlıkla yayımlanmasını önler.

## 1. Ekran görüntülerini hazırla

1. `python seed.py` ile sahte demo verisini oluştur.
2. Tarayıcıyı `1440 × 900` boyutuna ve `%100` yakınlaştırmaya getir.
3. Ayşe hesabıyla dashboard, staj takibi ve mentör inceleme ekranlarını aç.
4. Can hesabıyla kendi görevindeki teslim formunu aç.
5. Görselleri [ekran görüntüsü rehberindeki](screenshots/README.md) adlarla kaydet.
6. Görsellerde gerçek e-posta, telefon, şirket adı, bildirim veya token olmadığını
   ikinci kez kontrol et.
7. `README.md` içindeki dört görselin doğru yüklendiğini kontrol et.

## 2. Gönderilecek dosyaları incele

```powershell
git status --short
git check-ignore -v .env flowdesk.db server.stderr.log ornektesthesap.md
git diff --check
```

`.env`, `flowdesk.db`, sunucu logları, gerçek profil görselleri ve
`ornektesthesap.md` staged dosyalar arasında görünmemelidir.

## 3. Son test

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest
python -m flask --app run.py db current
python -m flask --app run.py db check
```

Beklenen sonuç: 84 test başarılı, migration `e27ca61b9054 (head)` ve model farkı
yok.

## 4. Commit oluştur

```powershell
git add .
git status --short
git diff --cached --stat
git diff --cached -- .env flowdesk.db
git commit -m "FlowDesk staj ve görev takip platformunu tamamla"
```

`git add .` sonrasında listeyi mutlaka okuyun. Gizli bir dosya görürseniz commit
oluşturmadan önce `git restore --staged DOSYA_ADI` kullanın.

## 5. GitHub'a gönder

Bu depo zaten aşağıdaki uzak adrese bağlıdır:

```text
https://github.com/yunopo42/FlowDesk---Ekip_ve_Gorev_Yonetim_Sistemi.git
```

Göndermek için:

```powershell
git push -u origin main
```

## 6. GitHub depo ayarları

Depo sayfasında **Settings** bölümünden görünürlüğü `Public` yapın. Ardından:

- Description: `Yazılım ekipleri, mentörler ve stajyerler için açık kaynak görev ve staj takip platformu.`
- Topics: `flask`, `python`, `task-management`, `internship-management`,
  `sqlalchemy`, `tailwindcss`, `pytest`
- Features: Issues açık
- Security: Private vulnerability reporting ve Dependabot alerts açık
- About: Releases ve Packages gerekmedikçe kapalı olabilir

İlk push'tan sonra **Actions** sekmesinde `Tests` workflow'unun yeşil olduğunu
doğrulayın. README rozeti de bundan sonra güncel test durumunu gösterecektir.
