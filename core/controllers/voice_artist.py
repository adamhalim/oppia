# coding: utf-8

# Copyright 2018 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Controllers for the translation changes."""

from __future__ import annotations

import io

from core import feconf
from core.constants import constants
from core.controllers import acl_decorators
from core.controllers import base
from core.domain import fs_services
from core.domain import rights_domain
from core.domain import rights_manager
from core.domain import user_services

import mutagen
from mutagen import mp3


class AudioUploadHandler(base.BaseHandler):
    """Handles audio file uploads (to Google Cloud Storage in production, and
    to the local datastore in dev).
    """

    URL_PATH_ARGS_SCHEMAS = {
        'exploration_id': {
            'schema': {
                'type': 'basestring',
                'validators': [{
                    'id': 'is_regex_matched',
                    'regex_pattern': constants.ENTITY_ID_REGEX
                }]
            }
        }
    }

    HANDLER_ARGS_SCHEMAS = {
        'POST': {
            'raw_audio_file': {
                'schema': {
                    'type': 'basestring',
                    'validators': [{
                        'id': 'is_valid_audio_file'
                    }]
                }
            },
            'filename': {
                'schema': {
                    'type': 'basestring',
                    'validators': [{
                        'id': 'is_regex_matched',
                        'regex_pattern': r'[^\s]+(\.(?i)(mp3))$'
                    }]
                }
            }
        }
    }

    # The string to prefix to the filename (before tacking the whole thing on
    # to the end of 'assets/').
    _FILENAME_PREFIX = 'audio'

    @acl_decorators.can_voiceover_exploration
    def post(self, exploration_id):
        """Saves an audio file uploaded by a content creator."""
        raw_audio_file = self.normalized_request.get('raw_audio_file')
        filename = self.normalized_payload.get('filename')

        tempbuffer = io.BytesIO()
        tempbuffer.write(raw_audio_file)
        tempbuffer.seek(0)
        audio = mp3.MP3(tempbuffer)
        tempbuffer.close()

        mimetype = audio.mime[0]
        # Fetch the audio file duration from the Mutagen metadata.
        duration_secs = audio.info.length

        # For a strange, unknown reason, the audio variable must be
        # deleted before opening cloud storage. If not, cloud storage
        # throws a very mysterious error that entails a mutagen
        # object being recursively passed around in app engine.
        del audio

        # Audio files are stored to the datastore in the dev env, and to GCS
        # in production.
        fs = fs_services.GcsFileSystem(
            feconf.ENTITY_TYPE_EXPLORATION, exploration_id)
        fs.commit(
            '%s/%s' % (self._FILENAME_PREFIX, filename),
            raw_audio_file, mimetype=mimetype)

        self.render_json({'filename': filename, 'duration_secs': duration_secs})


class StartedTranslationTutorialEventHandler(base.BaseHandler):
    """Records that this user has started the state translation tutorial."""

    @acl_decorators.can_play_exploration
    def post(self, unused_exploration_id):
        """Handles POST requests."""
        user_services.record_user_started_state_translation_tutorial(
            self.user_id)
        self.render_json({})


class VoiceArtistManagementHandler(base.BaseHandler):
    """Handles assignment of voice artists."""

    @acl_decorators.can_add_voice_artist
    def post(self, unused_entity_type, entity_id):
        """Handles Post requests."""
        voice_artist = self.payload.get('username')
        voice_artist_id = user_services.get_user_id_from_username(
            voice_artist)
        if voice_artist_id is None:
            raise self.InvalidInputException(
                'Sorry, we could not find the specified user.')
        rights_manager.assign_role_for_exploration(
            self.user, entity_id, voice_artist_id,
            rights_domain.ROLE_VOICE_ARTIST)

        self.render_json({})

    @acl_decorators.can_remove_voice_artist
    def delete(self, unused_entity_type, entity_id):
        """Handles Delete requests."""
        voice_artist = self.request.get('voice_artist')
        voice_artist_id = user_services.get_user_id_from_username(
            voice_artist)

        if voice_artist_id is None:
            raise self.InvalidInputException(
                'Sorry, we could not find the specified user.')
        rights_manager.deassign_role_for_exploration(
            self.user, entity_id, voice_artist_id)

        self.render_json({})
