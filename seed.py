"""FlowDesk demo verisi oluşturur.

Kullanım:
    python seed.py            # Demo kayıtları ekler, mevcut verilere dokunmaz
    python seed.py --reset    # Tüm tabloları boşaltıp demo veriyi yeniden kurar

Varsayılan çalıştırma güvenlidir: demo hesaplar e-posta adresine göre kontrol
edilir, zaten varsa yeniden oluşturulmaz. Kendi test hesaplarınız silinmez.
"""
import argparse
import sys
from datetime import date, datetime, time, timedelta

from app import create_app
from app.models import (
    Activity,
    Comment,
    DailyLog,
    Internship,
    Task,
    TASK_STATUS_LABELS,
    TaskSubmission,
    Team,
    TeamMember,
    User,
)
from app.models.base import utc_now
from extensions import db

DEMO_PASSWORD = 'Flowdesk2026!'

TODAY = date.today()


def due(day_offset):
    """Görev bitiş tarihini uygulamanın kullandığı biçimde üretir."""
    return datetime.combine(TODAY + timedelta(days=day_offset), time.max)


def ago(days, hours=0):
    return utc_now() - timedelta(days=days, hours=hours)


PERSONNEL = [
    ('ayse.yilmaz', 'ayse.yilmaz@flowdesk.local', '+90 532 000 00 01'),
    ('mehmet.demir', 'mehmet.demir@flowdesk.local', '+90 532 000 00 02'),
    ('zeynep.kaya', 'zeynep.kaya@flowdesk.local', '+90 532 000 00 03'),
]

INTERNS = [
    ('can.ozturk', 'can.ozturk@flowdesk.local', '+90 532 000 00 11'),
    ('elif.sahin', 'elif.sahin@flowdesk.local', '+90 532 000 00 12'),
    ('burak.aydin', 'burak.aydin@flowdesk.local', '+90 532 000 00 13'),
]


def reset_database():
    """Tüm tabloları boşaltır. Yalnızca --reset ile çağrılır."""
    for model in (
        Activity,
        Comment,
        TaskSubmission,
        DailyLog,
        Internship,
        Task,
        TeamMember,
        Team,
        User,
    ):
        db.session.query(model).delete()
    db.session.commit()


def create_user(username, email, phone, account_type):
    user = User(
        username=username,
        email=email,
        phone=phone,
        account_type=account_type,
        email_verified=True,
        email_verified_at=utc_now(),
        created_at=ago(60)
    )
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    return user


def build_users():
    """Demo hesapları oluşturur; var olanları yeniden kullanır."""
    users = {}
    created = []

    roster = (
        [(row, 'Personnel') for row in PERSONNEL]
        + [(row, 'Intern') for row in INTERNS]
    )

    for (username, email, phone), account_type in roster:
        existing = db.session.scalar(
            db.select(User).where(User.email == email)
        )

        if existing is None:
            existing = create_user(username, email, phone, account_type)
            created.append(email)

        users[username] = existing

    db.session.commit()
    return users, created


def add_member(team, user, role):
    membership = db.session.scalar(
        db.select(TeamMember).where(
            TeamMember.team_id == team.id,
            TeamMember.user_id == user.id
        )
    )

    if membership is None:
        membership = TeamMember(
            team_id=team.id,
            user_id=user.id,
            role=role,
            joined_at=ago(45)
        )
        db.session.add(membership)

    return membership


def build_team(name, description, roster):
    team = db.session.scalar(
        db.select(Team).where(Team.name == name)
    )

    if team is None:
        team = Team(
            name=name,
            description=description,
            created_at=ago(50)
        )
        db.session.add(team)
        db.session.flush()

    for user, role in roster:
        add_member(team, user, role)

    db.session.commit()
    return team


def build_task(
    team,
    creator,
    assignee,
    title,
    description,
    priority,
    status,
    due_date,
    created_days_ago
):
    task = db.session.scalar(
        db.select(Task).where(
            Task.team_id == team.id,
            Task.title == title
        )
    )

    if task is not None:
        return task, False

    task = Task(
        title=title,
        description=description,
        priority=priority,
        status=status,
        due_date=due_date,
        created_at=ago(created_days_ago),
        updated_at=ago(max(created_days_ago - 1, 0)),
        team_id=team.id,
        created_by_id=creator.id,
        assigned_to_id=assignee.id if assignee else None
    )
    db.session.add(task)
    db.session.flush()

    db.session.add(
        Activity(
            action='Görev oluşturuldu.',
            task_id=task.id,
            user_id=creator.id,
            created_at=ago(created_days_ago)
        )
    )

    if status != 'Todo':
        db.session.add(
            Activity(
                action=(
                    'Durum Yapılacak değerinden '
                    f'{TASK_STATUS_LABELS.get(status, status)} değerine '
                    'değiştirildi.'
                ),
                task_id=task.id,
                user_id=(assignee or creator).id,
                created_at=ago(max(created_days_ago - 2, 0))
            )
        )

    return task, True


def build_internship(team, intern, mentor, unit, role, start_offset,
                     end_offset, status):
    internship = db.session.scalar(
        db.select(Internship).where(
            Internship.team_id == team.id,
            Internship.intern_id == intern.id
        )
    )

    if internship is not None:
        return internship, False

    internship = Internship(
        team_id=team.id,
        intern_id=intern.id,
        mentor_id=mentor.id,
        company_unit=unit,
        internship_role=role,
        start_date=TODAY + timedelta(days=start_offset),
        end_date=TODAY + timedelta(days=end_offset),
        status=status,
        created_at=ago(abs(start_offset))
    )
    db.session.add(internship)
    db.session.flush()
    return internship, True


def build_daily_logs(internship):
    """Staj için çeşitli durumlarda günlük çalışma kayıtları üretir."""
    entries = [
        (
            12,
            'Proje kurulumu ve geliştirme ortamı',
            'Depoyu klonladım, sanal ortamı kurdum ve uygulamayı yerelde '
            'çalıştırdım. Veritabanı migrasyonlarını uyguladım.',
            'Flask uygulama fabrikası (create_app) deseninin neden '
            'kullanıldığını öğrendim.',
            '',
            '7.50',
            'Approved',
            'Kurulum notların çok düzenli, böyle devam et.'
        ),
        (
            11,
            'Kullanıcı modeli ve kimlik doğrulama incelemesi',
            'User modelini ve Flask-Login yapılandırmasını inceledim. '
            'Parola hash mekanizmasını adım adım takip ettim.',
            'Parolaların asla düz metin saklanmadığını, werkzeug ile '
            'hashlendiğini öğrendim.',
            'Oturum çerezinin nasıl imzalandığını tam kavrayamadım.',
            '8.00',
            'Approved',
            'Çerez imzalama konusunu yarın birlikte gözden geçirelim.'
        ),
        (
            8,
            'Görev listesi filtreleri',
            'Görev listesindeki durum ve öncelik filtrelerini inceledim, '
            'eksik durum seçeneklerini not ettim.',
            'SQLAlchemy sorgularının koşula göre nasıl zincirlendiğini '
            'öğrendim.',
            '',
            '8.00',
            'Revision Requested',
            'Hangi filtrenin hangi sorguya karşılık geldiğini örnekle yaz.'
        ),
        (
            4,
            'Birim testleri okuma',
            'tests klasöründeki testleri okuyup pytest ile çalıştırdım. '
            'Fixture yapısını çıkardım.',
            'conftest.py içindeki fixture zincirinin testlere nasıl veri '
            'sağladığını öğrendim.',
            '',
            '6.50',
            'Submitted',
            None
        ),
        (
            1,
            'Görev teslim akışı',
            'Stajyer teslim formunu ve mentör onay akışını uçtan uca '
            'denedim.',
            'Durum makinesinin (Todo → İnceleme → Tamamlandı) nasıl '
            'kurgulandığını öğrendim.',
            'Teslim sonrası durumu geri alamıyorum, doğrusu bu mu?',
            '8.00',
            'Submitted',
            None
        ),
    ]

    created = 0
    for (days_ago, title, summary, learned, blockers, hours, status,
         feedback) in entries:
        work_date = TODAY - timedelta(days=days_ago)

        if work_date < internship.start_date:
            continue

        exists = db.session.scalar(
            db.select(DailyLog).where(
                DailyLog.internship_id == internship.id,
                DailyLog.work_date == work_date
            )
        )
        if exists:
            continue

        db.session.add(
            DailyLog(
                internship_id=internship.id,
                work_date=work_date,
                title=title,
                work_summary=summary,
                learned=learned or None,
                blockers=blockers or None,
                hours=hours,
                status=status,
                mentor_feedback=feedback,
                reviewed_at=(
                    ago(days_ago - 1) if status != 'Submitted' else None
                ),
                created_at=ago(days_ago),
                updated_at=ago(days_ago)
            )
        )
        created += 1

    return created


def seed(reset):
    if reset:
        reset_database()

    users, created_users = build_users()

    ayse = users['ayse.yilmaz']
    mehmet = users['mehmet.demir']
    zeynep = users['zeynep.kaya']
    can = users['can.ozturk']
    elif_ = users['elif.sahin']
    burak = users['burak.aydin']

    dev_team = build_team(
        'Yazılım Geliştirme Ekibi',
        'Web uygulamaları ve iç servislerin geliştirilmesinden sorumlu ekip.',
        [
            (ayse, 'Admin'),
            (mehmet, 'Member'),
            (can, 'Intern'),
            (elif_, 'Intern'),
        ]
    )

    qa_team = build_team(
        'Test ve Kalite Ekibi',
        'Yazılım doğrulama, test otomasyonu ve kalite süreçleri ekibi.',
        [
            (zeynep, 'Admin'),
            (mehmet, 'Member'),
            (burak, 'Intern'),
        ]
    )

    task_plan = [
        # (ekip, oluşturan, atanan, başlık, açıklama, öncelik, durum,
        #  bitiş günü, kaç gün önce oluşturuldu)
        (
            dev_team, ayse, can,
            'Giriş ekranına kaba kuvvet koruması ekle',
            'Başarısız giriş denemeleri için oran sınırlaması uygulanacak. '
            'Sınır aşıldığında kullanıcıya anlaşılır bir uyarı gösterilmeli.',
            'High', 'Done', due(-3), 14
        ),
        (
            dev_team, ayse, can,
            'Görev listesi filtrelerini tamamla',
            'Durum filtresine inceleme bekleyen ve düzeltme istenen '
            'seçenekleri eklenecek; etiketler Türkçeleştirilecek.',
            'Medium', 'Review Pending', due(2), 6
        ),
        (
            dev_team, ayse, elif_,
            'Profil fotoğrafı yükleme doğrulaması',
            'Yüklenen dosyanın gerçekten resim olduğu doğrulanacak ve '
            'WebP biçimine dönüştürülerek saklanacak.',
            'High', 'Revision Requested', due(-1), 9
        ),
        (
            dev_team, mehmet, elif_,
            'Dashboard istatistik kartlarını iyileştir',
            'Gecikmiş ve yaklaşan görev sayıları ayrı kartlarda '
            'gösterilecek.',
            'Low', 'In Progress', due(7), 4
        ),
        (
            dev_team, ayse, mehmet,
            'Veritabanı yedekleme betiği yaz',
            'Günlük yedek alan ve son 7 yedeği saklayan bir betik '
            'hazırlanacak.',
            'Medium', 'Todo', due(12), 2
        ),
        (
            dev_team, mehmet, can,
            'E-posta doğrulama akışını belgele',
            'Kayıt, doğrulama ve yeniden gönderme adımları README '
            'dosyasına yazılacak.',
            'Low', 'Todo', due(-2), 11
        ),
        (
            qa_team, zeynep, burak,
            'Giriş akışı için test senaryoları hazırla',
            'Geçerli giriş, hatalı parola ve doğrulanmamış hesap '
            'senaryoları yazılacak.',
            'High', 'In Progress', due(3), 5
        ),
        (
            qa_team, zeynep, burak,
            'Yetkilendirme testlerini gözden geçir',
            'Ekip dışı kullanıcıların görev ve staj kayıtlarına '
            'erişemediği doğrulanacak.',
            'Medium', 'Todo', due(9), 3
        ),
        (
            qa_team, zeynep, mehmet,
            'Test raporu şablonu oluştur',
            'Haftalık test sonuçlarının paylaşılacağı şablon hazırlanacak.',
            'Low', 'Done', due(-5), 15
        ),
    ]

    tasks = {}
    new_tasks = 0
    for (team, creator, assignee, title, description, priority, status,
         due_date, created_days_ago) in task_plan:
        task, is_new = build_task(
            team, creator, assignee, title, description, priority,
            status, due_date, created_days_ago
        )
        tasks[title] = task
        new_tasks += int(is_new)

    db.session.commit()

    # Yorumlar
    comment_plan = [
        (
            'Giriş ekranına kaba kuvvet koruması ekle',
            can,
            'Oran sınırlamasını Flask-Limiter ile ekledim. Sınırı yalnızca '
            'başarısız denemelerde artırıyorum.',
            5
        ),
        (
            'Giriş ekranına kaba kuvvet koruması ekle',
            ayse,
            'Doğru yaklaşım. Başarılı girişin sayacı tüketmemesi önemliydi, '
            'teşekkürler.',
            4
        ),
        (
            'Profil fotoğrafı yükleme doğrulaması',
            elif_,
            'Pillow ile doğrulama ekledim ancak çok büyük dosyalarda '
            'zaman aşımı alıyorum.',
            3
        ),
        (
            'Profil fotoğrafı yükleme doğrulaması',
            ayse,
            'Yükleme boyutu sınırını 5 MB olarak ayarladık, onu da '
            'kontrol et.',
            2
        ),
        (
            'Giriş akışı için test senaryoları hazırla',
            burak,
            'Hatalı parola senaryosunu yazdım, doğrulanmamış hesap '
            'senaryosuna geçiyorum.',
            1
        ),
    ]

    new_comments = 0
    for title, author, content, days_ago in comment_plan:
        task = tasks[title]
        exists = db.session.scalar(
            db.select(Comment).where(
                Comment.task_id == task.id,
                Comment.user_id == author.id,
                Comment.content == content
            )
        )
        if exists:
            continue

        db.session.add(
            Comment(
                content=content,
                task_id=task.id,
                user_id=author.id,
                created_at=ago(days_ago)
            )
        )
        new_comments += 1

    db.session.commit()

    # Staj programları
    can_internship, _ = build_internship(
        dev_team, can, ayse, 'Yazılım Geliştirme',
        'Backend Stajyeri', -14, 31, 'Active'
    )
    elif_internship, _ = build_internship(
        dev_team, elif_, ayse, 'Yazılım Geliştirme',
        'Frontend Stajyeri', -10, 35, 'Active'
    )
    burak_internship, _ = build_internship(
        qa_team, burak, zeynep, 'Test ve Kalite',
        'Test Otomasyon Stajyeri', -7, 38, 'Active'
    )
    db.session.commit()

    new_logs = build_daily_logs(can_internship)
    new_logs += build_daily_logs(elif_internship)
    db.session.commit()

    # Görev teslimleri
    submission_plan = [
        (
            'Giriş ekranına kaba kuvvet koruması ekle',
            can, ayse,
            'Giriş ucuna Flask-Limiter ile 15 dakikada 10 deneme sınırı '
            'ekledim. Sayaç yalnızca başarısız denemelerde artıyor, böylece '
            'doğru parolayla giren kullanıcı kilitlenmiyor.',
            'feat(auth): giris denemelerine oran sinirlamasi ekle',
            'https://github.com/ornek/flowdesk/commit/9f2c1ab',
            'Başarılı ve başarısız denemeleri ayırt etmek için deduct_when '
            'kullanmam gerektiğini anlamam zaman aldı.',
            'Oran sınırlamasının yalnızca istenen durumlarda sayaç '
            'artırabildiğini öğrendim.',
            'Approved',
            'Temiz çözüm, testleri de eklediğin için ayrıca teşekkürler.',
            5
        ),
        (
            'Görev listesi filtrelerini tamamla',
            can, None,
            'Durum filtresine inceleme bekleyen ve düzeltme istenen '
            'seçeneklerini ekledim. Etiketleri tek bir sözlükten okuyacak '
            'şekilde Türkçeleştirdim.',
            'feat(tasks): eksik durum filtrelerini ekle',
            'https://github.com/ornek/flowdesk/pull/42',
            'Durum metinlerinin şablonlarda tekrar etmesi kafa '
            'karıştırıcıydı.',
            'Sabitleri tek bir yerde tutmanın bakımı kolaylaştırdığını '
            'öğrendim.',
            'Pending Review',
            None,
            1
        ),
        (
            'Profil fotoğrafı yükleme doğrulaması',
            elif_, ayse,
            'Yüklenen dosyayı Pillow ile doğrulayıp WebP biçimine '
            'dönüştürüyorum.',
            'feat(profile): fotograf yuklemeyi dogrula',
            'https://github.com/ornek/flowdesk/commit/3ad77e1',
            'EXIF yönlendirmesi olan fotoğraflar ters kaydediliyordu.',
            'Dosya uzantısına güvenilmeyeceğini, içeriğin doğrulanması '
            'gerektiğini öğrendim.',
            'Revision Requested',
            'Dosya adını kullanıcıdan gelen değerle oluşturmuyorsun, iyi. '
            'Ancak eski fotoğrafın silinmesini de ekle.',
            3
        ),
    ]

    new_submissions = 0
    for (title, submitter, reviewer, summary, commit_message, work_url,
         challenges, learned, status, feedback, days_ago) in submission_plan:
        task = tasks[title]
        exists = db.session.scalar(
            db.select(TaskSubmission).where(
                TaskSubmission.task_id == task.id,
                TaskSubmission.commit_message == commit_message
            )
        )
        if exists:
            continue

        db.session.add(
            TaskSubmission(
                task_id=task.id,
                submitted_by_id=submitter.id,
                reviewed_by_id=reviewer.id if reviewer else None,
                summary=summary,
                commit_message=commit_message,
                work_url=work_url,
                challenges=challenges,
                learned=learned,
                status=status,
                mentor_feedback=feedback,
                created_at=ago(days_ago),
                reviewed_at=ago(days_ago - 1) if reviewer else None
            )
        )
        new_submissions += 1

    db.session.commit()

    return {
        'users': len(created_users),
        'tasks': new_tasks,
        'comments': new_comments,
        'logs': new_logs,
        'submissions': new_submissions,
        'internships': [can_internship, elif_internship, burak_internship],
    }


def report(result):
    print()
    print('=' * 70)
    print('DEMO VERİSİ HAZIR')
    print('=' * 70)
    print(f'  Yeni kullanıcı   : {result["users"]}')
    print(f'  Yeni görev       : {result["tasks"]}')
    print(f'  Yeni yorum       : {result["comments"]}')
    print(f'  Yeni günlük kayıt: {result["logs"]}')
    print(f'  Yeni teslim      : {result["submissions"]}')
    print()
    print(f'  Tüm demo hesapların parolası: {DEMO_PASSWORD}')
    print()
    print('  YAZILIM PERSONELİ (ekip ve görev yönetebilir, mentör olabilir)')
    for username, email, _ in PERSONNEL:
        print(f'    {email:<34} ({username})')
    print()
    print('  STAJYER (yalnızca kendi görevlerini görür)')
    for username, email, _ in INTERNS:
        print(f'    {email:<34} ({username})')
    print()
    print('  Önerilen ilk giriş: ayse.yilmaz@flowdesk.local')
    print('  (Yazılım Geliştirme Ekibi Admin + iki stajyerin mentörü)')
    print('=' * 70)


def main():
    parser = argparse.ArgumentParser(
        description='FlowDesk demo verisi oluşturur.'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Tüm tabloları boşaltıp demo veriyi sıfırdan kurar.'
    )
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        if args.reset:
            print(
                'UYARI: --reset tüm kullanıcı, ekip, görev ve staj '
                'kayıtlarını siler.'
            )
            answer = input('Devam etmek için "evet" yazın: ').strip().lower()
            if answer != 'evet':
                print('İşlem iptal edildi.')
                return 1

        report(seed(reset=args.reset))

    return 0


if __name__ == '__main__':
    sys.exit(main())
