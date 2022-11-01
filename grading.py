class get_grade:
    def __init__(self, grade):
        self.grade = grade

    def letter_grade(self):
        grade = self.grade

        if grade >= 90:
            return 'A+'
        elif grade >= 85:
            return 'A'
        elif grade >= 80:
            return 'A-'
        elif grade >= 77:
            return 'B+'
        elif grade >= 73:
            return 'B'
        elif grade >= 70:
            return 'B-'
        elif grade >= 67:
            return 'C+'
        elif grade >= 63:
            return 'C'
        elif grade >= 60:
            return 'C-'
        elif grade >= 57:
            return 'D+'
        elif grade >= 53:
            return 'D'
        elif grade >= 50:
            return 'D-'
        else:
            return 'F'

    def color(self):
        grade = self.grade

        if grade >= 90:
            return 0x92DCBA
        elif grade >= 85:
            return 0X20D6C7
        elif grade >= 80:
            return 0X249FDE
        elif grade >= 77:
            return 0xD6F264
        elif grade >= 73:
            return 0x59C135
        elif grade >= 70:
            return 0x328464
        elif grade >= 67:
            return 0xFFFC40
        elif grade >= 63:
            return 0xFFD541
        elif grade >= 60:
            return 0xF9A31B
        elif grade >= 57:
            return 0xF5A097
        elif grade >= 53:
            return 0x793A80
        elif grade >= 50:
            return 0x242234
        else:
            return 0x6D758D