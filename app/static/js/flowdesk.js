/* FlowDesk genel arayüz davranışları.
 *
 * Bu dosya harici olarak yüklenir. İçerik Güvenlik Politikası (CSP) satır içi
 * betiklere ve onclick/onsubmit gibi satır içi olay yakalayıcılara izin
 * vermediği için tüm davranışlar buradan bağlanır.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // Geri dön düğmeleri: <button data-action="history-back">
        document
            .querySelectorAll('[data-action="history-back"]')
            .forEach(function (button) {
                button.addEventListener('click', function () {
                    window.history.back();
                });
            });

        // Onay isteyen formlar: <form data-confirm="Emin misiniz?">
        document
            .querySelectorAll('form[data-confirm]')
            .forEach(function (form) {
                form.addEventListener('submit', function (event) {
                    if (!window.confirm(form.dataset.confirm)) {
                        event.preventDefault();
                    }
                });
            });

        // Profil fotoğrafı ön izlemesi.
        var imageInput = document.getElementById('profile_image');

        if (imageInput) {
            var imagePreview = document.getElementById('profile-preview');
            var imagePlaceholder = document.getElementById(
                'profile-placeholder'
            );
            var fileHelp = document.getElementById('file-help');

            imageInput.addEventListener('change', function () {
                var file = imageInput.files[0];

                if (!file) {
                    return;
                }

                if (imagePreview) {
                    imagePreview.src = URL.createObjectURL(file);
                    imagePreview.classList.remove('hidden');
                }

                if (imagePlaceholder) {
                    imagePlaceholder.classList.add('hidden');
                }

                if (fileHelp) {
                    fileHelp.textContent =
                        file.name +
                        ' seçildi. Kaydettiğinde fotoğrafın güncellenecek.';
                }
            });
        }
    });
})();
