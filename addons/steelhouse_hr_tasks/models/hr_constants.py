"""Shared lists of the HR processes (no models here)."""
KINDS = [('vacancy', 'ვაკანსიის განთავსება'), ('hire', 'ახალი თანამშრომლის აყვანა'),
         ('dismissal', 'თანამშრომლის გათავისუფლება')]
# the fields each process shows on the form - HR chooses which of them are required (settings)
CANDIDATES = {
    'vacancy': ['sh_hr_position', 'sh_hr_duties', 'sh_hr_requirements', 'sh_hr_workplace', 'sh_hr_schedule',
                'sh_hr_salary'],
    'hire': ['sh_hr_id_number', 'sh_hr_phone', 'sh_hr_address', 'sh_hr_bank_account', 'sh_hr_email',
             'sh_hr_position', 'sh_hr_salary', 'sh_hr_schedule', 'sh_hr_start_date', 'sh_hr_legal_entity_id'],
    'dismissal': ['sh_hr_application', 'sh_hr_reason', 'sh_hr_special', 'sh_hr_last_day', 'sh_hr_property',
                  'sh_hr_legal_entity_id'],
}
ALL_CANDIDATES = sorted({f for fs in CANDIDATES.values() for f in fs})
# first filling of the settings: the client's documents (2026-11-25)
DEFAULT_REQUIRED = {
    'vacancy': CANDIDATES['vacancy'],
    'hire': CANDIDATES['hire'],
    'dismissal': ['sh_hr_application', 'sh_hr_reason', 'sh_hr_special', 'sh_hr_last_day', 'sh_hr_property'],
}
ASSIGNEES = [('lawyer', 'იურიდიული პირის იურისტი'), ('accountant', 'იურიდიული პირის ბუღალტერი'),
             ('users', 'არჩეული ადამიანები'), ('department', 'დეპარტამენტი (ხელმძღვანელ(ებ)ი)')]
