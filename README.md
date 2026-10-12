# The Puppeteer

Distrobox için mor ağırlıklı, yerel Linux masaüstü uygulaması. **0.1.0 — ilk geliştirme sürümü.**

Qt 6 / QML ve PySide6 kullanır. Tarayıcı veya Electron gerektirmez.

## Hızlı başlatma

Arşivi aç, klasörün içinde terminal aç:

```sh
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

`setup.sh` ve `run.sh`, önce bu klasördeki `.venv` ortamını, ardından PATH üzerindeki `python3` ve `/usr/bin/python3` kurulumlarını denetler. Uygulamanın ihtiyaç duyduğu Qt modüllerini yükleyebilen ilk Python kullanılır; eksik bir `.venv`, çalışan sistem kurulumunu engellemez. Uygun ortam yoksa `setup.sh` yalnızca bu klasörde `.venv` oluşturup PySide6'yı kurar. Distrobox veya Podman'ı bu betik kurmaz. Uygulamadaki **Kurulum** ekranı eksik bileşenler için paket işlemini gösterir ve terminalde başlatır.

Başlatma başarısızsa hata çıktısında denenen Python yolu ve eksik Qt modülü/paylaşımlı kütüphane gösterilir. Yalnızca `import PySide6` kontrolünün başarılı olması tüm Qt bileşenlerinin çalıştığı anlamına gelmez.

Python 3.10+ gerekir. PySide6 6.10.2 ile test edildi. Pip sürümünün Qt paketlerini indirebilmesi için internet gerekir. Debian/Ubuntu'da venv yoksa `python3-venv` paketini kur. Çok eski glibc sistemlerinde dağıtımın kendi PySide6 paketini kullan veya desteklenen bir PySide6 sürümü seç.

Uygulamayı **normal kullanıcı hesabından** çalıştır; `sudo ./run.sh` kullanma. Sistem paket kurulumunda terminalde sudo istenir.

### Arch / CachyOS

Sistemde PySide6'yı paket yöneticisinden sağlamak istersen:

```sh
sudo pacman -S --needed pyside6
./run.sh
```

Distrobox ve Podman için uygulamanın Kurulum ekranını kullanabilirsin; mevcut kurulumla doğrudan da çalışır. Rootless Podman erişimi ayrıca doğrulanır. `/etc/subuid`, `/etc/subgid`, kullanıcı oturumu veya motor yapılandırması sorunlarında motorun resmi yönergesini kullan. Uygulama bu dosyaları otomatik değiştirmez.

### Demo modu

```sh
./run.sh --demo
```

Örnek ortamlarla arayüzü inceleyebilirsin. Distrobox, Podman veya Docker işlemleri çalıştırılmaz; sistem ayarları yazılmaz. Başlıkta ve durum çubuğunda DEMO belirtilir.

### Masaüstü menüsü

Klasörü kalıcı konumuna yerleştirdikten sonra:

```sh
python3 packaging/install-launcher.py
```

Kullanıcının uygulama menüsüne The Puppeteer kısayolunu ekler. Klasörü taşırsan betiği yeniden çalıştır.

## Sistemden kaldırma

Önce uygulamayı kapat ve devam eden terminal işlerinin bitmesini bekle. Uygulama klasöründe:

```sh
chmod +x uninstall.sh
./uninstall.sh
```

Betiğin gösterdiği kaldırma planını onayladıktan sonra bu sürümün bilinen uygulama dosyaları, bu klasöre ait menü kısayolu ve `setup.sh` tarafından işaretlenmiş özel `.venv` kaldırılır. Kaynak klasörü yalnızca boş kaldığında silinir; başka kullanıcı dosyaları ve Git deposu korunur. Distrobox, Podman/Docker ve sistemdeki PySide6 paketi kaldırılmaz.

Önizleme ve isteğe bağlı ayar temizliği:

```sh
./uninstall.sh --dry-run
./uninstall.sh --purge
```

`--purge`, The Puppeteer ayarlarını ve işlem kayıtlarını da siler. Konteynerler ve `the-puppeteer/homes` içindeki ev dizinleri bu seçenekte de korunur.

Kaynak kodu geliştirme için tutmak istersen `--keep-source` kullan. İlk arşivdeki eski `.venv` işaretsiz olduğu için otomatik kaldırılmaz; yalnızca bu uygulamaya özel olduğundan eminsen `--remove-venv` seçeneğini ekle. `--yes` gösterilen planı etkileşimli soru sormadan uygular. Betiği `sudo` ile çalıştırma.

Wheel kurulumunda, kurulumun yapıldığı venv'deki `the-puppeteer-uninstall` komutunu çalıştırabilir veya kaynak betiğe `--python /tam/yol/venv/bin/python` verebilirsin. Yalnızca kullanıcıya ait pip/venv kurulumu kaldırılır; sistem paket yöneticisinin veya sistem Python'unun kurulumuna müdahale edilmez.

## Çalışan özellikler

- Mor/lavanta açık tema, mürdüm koyu tema ve sistem temasını takip etme.
- Türkçe/İngilizce arayüz; bazı işlem/hata açıklamaları bu sürümde Türkçedir.
- Ana dağıtım ailesini ve mevcut Distrobox / Podman / Docker erişimini algılama.
- Arch, Fedora, Debian/Ubuntu ve openSUSE ailesi için eksik paketlerin kurulum planı.
- Kurulumu terminalde, paket yöneticisinin gerçek soruları ve sudo istemiyle çalıştırma.
- Podman ve mevcut Docker motoru arasında seçim; her komuta doğru motorun aktarılması.
- Gerçek Distrobox ortamlarını listeleme; motor değişiminde envanteri yenileme.
- İmaj adresini/sürümünü düzenleyerek oluşturma; ayrı ev dizini, Git/CMake ve NVIDIA seçeneği.
- Oluşturmanın ardından ilk giriş hazırlığı; bu aşama bitmeden iş tamamlanmış sayılmaz.
- Terminal açma, başlatma, durdurma, paket güncelleme, durdurulmuş ortamı klonlama.
- Konteyner içindeki kurulu `.desktop` uygulamalarını keşfetme; menüye ekleme/kısayol kaldırma.
- Ortam adı yazılarak silme; `--rm-home` kullanılmadığı için ev dizini korunur.
- İşlem aşaması, çıkış kodu, komut/çıktı kaydı, geçmiş ve işlem iptali.
- Terminalde çalışan işi uygulama yeniden açıldığında yeniden izleme.
- Ctrl+N: yeni ortam; Ctrl+R: yeniden denetleme.

Uygulamaları taramak durdurulmuş konteyneri başlatabilir. İlk açılış yarıda kaldıysa önce **Terminal aç** ile hazırlığı tamamla.

Paket güncelleme, dağıtımın ana sürüm yükseltmesi değildir. Klonlama, ev dizinindeki tüm dosyaların yedeği değildir. Ayrı HOME ana sistem dosyalarına erişimi engellemez; Distrobox güvenlik sandbox'ı değildir.

## İlk sürümün sınırları

- Gerçek Podman/Docker veya dağıtım paket kurulumları bu geliştirme ortamında uçtan uca denenmedi. Native Qt/QML ve gerçek süreç yürütme, geçici sahte CLI araçlarıyla test edildi. Kendi sistemindeki ilk işlemde terminal sonucunu kontrol et.
- Podman rootless varsayılandır ve işlem öncesi doğrulanır. Yeni Docker servisi kurma/yapılandırma bu sürümde yoktur; mevcut Docker erişimi desteklenir.
- NixOS ve değişmez sistemlerde otomatik paket kurulumu uygulanmaz; resmi yönerge açılır.
- İmaj etiketlerinin registry/mimari/digest denetimi henüz yoktur. Değişken `latest`/`stable` etiketleri sabit sürüm garantisi vermez. İmaj uyumsuzluğu Distrobox tarafından hata olarak döner.
- Distrobox tarafından belgelenen `ID | NAME | STATUS | IMAGE` liste biçimi kullanılır. Tanınmayan biçim görünür hatadır; başka konteynerler üzerinde işlem tahmin edilmez.
- Önceden başka araçlarla oluşturulmuş konteynerlerin özel ev dizini kayıtları bilinmiyorsa "kayıt yok" gösterilir.
- Silme öncesinde yalnızca seçili ortam için bu oturumda keşfedilmiş, dışa aktarımı doğrulanmış uygulama kısayolları temizlenir. Diğer kısayolları silmeden önce Uygulamalar ekranında tara. Kısayol temizliği başarısızsa konteyner silme aşamasına geçilmez.
- İptal, daha önce tamamlanmış paket değişikliklerini geri almaz. CLI sonlandırılsa bile motorun tamamladığı işler olabilir; envanter yeniden okunur.
- Tam `.deb`/`.rpm`/Flatpak paketleri, sürüm/mimari kataloğu ve kapsamlı yedek akışı sonraki geliştirme aşamasıdır.

## Ayarlar ve kayıtlar

Tercihler: `$XDG_CONFIG_HOME/the-puppeteer/settings.json`.
Uygulamanın oluşturduğu ortamların HOME kayıtları: aynı klasörde `environments.json`.
İşlem kayıtları: `$XDG_DATA_HOME/the-puppeteer/jobs/<id>/`.
Özel ortam ev dizinleri: `$XDG_DATA_HOME/the-puppeteer/homes/<ad>/`.

XDG değişkenleri yoksa standart `~/.config` ve `~/.local/share` kullanılır. Uygulama kaldırıldığında bu dizinler ve gerçek konteynerler kendiliğinden silinmez.

## Geliştirme ve test

```sh
python3 -m unittest discover -s tests -p test_core.py -v
```

Native Qt/QML testleri (PySide6 kurulu Python ile):

```sh
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python3 -m unittest discover -s tests -v
```

Venv kullanıyorsan `python3` yerine `.venv/bin/python` kullan.

Testler isim/komut enjeksiyonu, çakışan isim, silme onayı ve HOME koruması, özel yollar, uygulama dosyaları, kısayol eşleştirme, kurulum planı, başarısız adımın sonraki adımları durdurması, süreç zaman aşımı, gerçek QProcess adaptörü ve QML oluşturma/silme/tema/dil akışlarını kapsar. Gerçek konteyner veya sistem paketi oluşturmaz.

Wheel oluşturmak için:

```sh
python3 -m pip install build
python3 -m build
```

Bu komutları bir geliştirme venv'inde çalıştır.

## Kaynaklar

- https://distrobox.it/
- https://distrobox.it/usage/distrobox-create/
- https://distrobox.it/usage/distrobox-enter/
- https://distrobox.it/usage/distrobox-rm/
- https://distrobox.it/usage/distrobox-export/
- https://doc.qt.io/qtforpython-6/

Lisans: MIT.
