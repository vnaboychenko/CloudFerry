# Copyright 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

from marshmallow import fields
from marshmallow import exceptions

from cloudferrylib.os.discovery import keystone
from cloudferrylib.os.discovery import model

LOG = logging.getLogger(__name__)


class ImageMember(model.Model):
    class Schema(model.Schema):
        member_id = fields.String(required=True)
        can_share = fields.Boolean(required=True)


class Image(model.Model):
    class Schema(model.Schema):
        object_id = model.PrimaryKey('id')
        name = fields.String(required=True)
        tenant = model.Dependency(keystone.Tenant, required=True,
                                  load_from='owner', dump_to='owner')
        checksum = fields.String(required=True, allow_none=True)
        size = fields.Integer(required=True)
        virtual_size = fields.Integer(required=True, allow_none=True,
                                      missing=None)
        is_public = fields.Boolean(required=True)
        protected = fields.Boolean(required=True)
        container_format = fields.String(required=True)
        disk_format = fields.String(required=True)
        min_disk = fields.Integer(required=True)
        min_ram = fields.Integer(required=True)
        properties = fields.Dict()
        members = model.Nested(ImageMember, many=True, missing=list)

    @classmethod
    def load_missing(cls, cloud, object_id):
        image_client = cloud.image_client()
        raw_image = image_client.images.get(object_id.id)
        image = Image.load_from_cloud(cloud, raw_image)
        for member in image_client.image_members.list(image=raw_image):
            image.members.append(ImageMember.load_from_cloud(cloud, member))
        return image

    @classmethod
    def discover(cls, cloud):
        image_client = cloud.image_client()
        with model.Transaction() as tx:
            for raw_image in image_client.images.list(
                    filters={"is_public": None}):
                try:
                    image = Image.load_from_cloud(cloud, raw_image)
                    members_list = image_client.image_members.list(
                        image=raw_image)
                    for member in members_list:
                        image.members.append(
                            ImageMember.load_from_cloud(cloud, member))
                    tx.store(image)
                except exceptions.ValidationError as e:
                    LOG.warning('Invalid image %s: %s', raw_image.id, e)
