from django.conf import settings
from storages.backends.gcloud import GoogleCloudStorage

class StaticStorage(GoogleCloudStorage):
    location = "static"
    # default_acl = "publicRead"

class MediaStorage(GoogleCloudStorage):
    location = "media"
    # default_acl = "publicRead"







#AWS
#from storages.backends.s3boto3 import S3boto3Storage

#class StaticStorage(S3boto3Storage):
#    location = 'static'
#    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN