from mongoengine import DynamicDocument, StringField

class JobOpening(DynamicDocument):
    case_id = StringField(required=True, unique=True)
    job_id = StringField(required=True, unique=True)


class JobSeeker(DynamicDocument):
    case_id = StringField(required=True, unique=True)


class Firm(DynamicDocument):
    case_id = StringField(required=True, unique=True)


class Match(DynamicDocument):
    case_id = StringField(required=True, unique=True)