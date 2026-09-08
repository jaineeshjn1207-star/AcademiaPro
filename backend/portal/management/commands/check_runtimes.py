import shutil
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Checks whether the Python, C++ (g++), Java (javac/java) and Node.js "
        "toolchains needed by the coding-exam runner are installed on this server."
    )

    CHECKS = [
        ('Python 3', ['python3'], sys.executable),
        ('C++ compiler (g++)', ['g++'], None),
        ('Java compiler (javac)', ['javac'], None),
        ('Java runtime (java)', ['java'], None),
        ('Node.js (javascript)', ['node'], None),
    ]

    def handle(self, *args, **options):
        all_ok = True
        for label, bins, fallback in self.CHECKS:
            ok = all(shutil.which(b) for b in bins)
            path = shutil.which(bins[0]) or ''
            if not ok and fallback and label == 'Python 3':
                ok = True
                path = fallback
            all_ok = all_ok and ok
            status = self.style.SUCCESS('OK') if ok else self.style.ERROR('MISSING')
            self.stdout.write(f"  {label:<26} [{status}]  {path}")

        self.stdout.write('')
        if all_ok:
            self.stdout.write(self.style.SUCCESS('All coding-exam runtimes are available.'))
        else:
            self.stdout.write(self.style.WARNING(
                'One or more runtimes are missing. Install them on the server or run scripts/install_runtimes.sh on Ubuntu/Debian.'
            ))


