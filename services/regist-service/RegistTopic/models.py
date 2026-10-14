from django.db import models

class Registration(models.Model):
    registration_id = models.CharField(db_column="RegistrationId", primary_key=True, max_length=255)
    student_id = models.CharField(db_column="StudentId", max_length=255, null=True)
    topic_id = models.CharField(db_column="TopicId", max_length=255, null=True)
    semester = models.TextField(db_column="Semester", null=True, blank=True)
    status = models.IntegerField(db_column="Status", null=True)
    notes = models.TextField(db_column="Notes", null=True, blank=True)
    reason = models.TextField(db_column="Reason", null=True, blank=True)
    point = models.DecimalField(db_column="Point", max_digits=4, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(db_column="CreatedAt", null=True)
    updated_at = models.DateTimeField(db_column="UpdatedAt", null=True)
    updated_by = models.CharField(db_column="UpdatedBy", max_length=255, null=True)

    class Meta:
        managed = False
        db_table = "Registrations"
        ordering = ["-created_at", "registration_id"]
