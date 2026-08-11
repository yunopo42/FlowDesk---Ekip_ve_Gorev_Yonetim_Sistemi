# FlowDesk'e katkıda bulunma

Katkınız için teşekkürler. Küçük düzeltmelerden yeni özellik önerilerine kadar
her katkı değerlidir.

## Geliştirme akışı

1. Depoyu fork edin ve yerel makinenize klonlayın.
2. `main` üzerinden açıklayıcı isimli bir branch açın:
   `git switch -c feature/kisa-aciklama`
3. README'deki yerel kurulum adımlarını uygulayın.
4. Değişikliğiniz için test ekleyin veya mevcut testleri güncelleyin.
5. `python -m pytest` komutunun başarıyla tamamlandığını doğrulayın.
6. Küçük ve anlamlı commit'ler oluşturup pull request açın.

## Kod ve commit ilkeleri

- İş mantığını route içinde gereksiz yere çoğaltmayın.
- Yetki kontrollerini yalnızca arayüzde değil backend tarafında da uygulayın.
- Kullanıcı girdisini doğrulayın; SQLAlchemy sorgularını tercih edin.
- Gizli anahtar, `.env`, gerçek kullanıcı verisi veya yerel veritabanı eklemeyin.
- Commit mesajını emir kipinde ve değişikliği açıklayacak şekilde yazın.

## Hata bildirimi

Hatanın tekrar üretim adımlarını, beklenen ve gerçekleşen sonucu, kullanılan
Python sürümünü ve mümkünse kişisel veri içermeyen ekran görüntüsünü ekleyin.
Güvenlik açıklarını herkese açık issue yerine [SECURITY.md](SECURITY.md)
üzerindeki süreçle bildirin.
