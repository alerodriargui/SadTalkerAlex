import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import app as application


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()
        application.jobs.clear()

    def test_invalid_input_and_unknown_video(self):
        self.assertEqual(self.client.post('/api/jobs').status_code, 400)
        self.assertEqual(self.client.get('/api/jobs/unknown/video').status_code, 404)

    def test_missing_engine_is_reported(self):
        with patch.object(application, 'readiness', return_value=['Falta el modelo.']):
            result = self.client.get('/api/health')
            self.assertFalse(result.json['ready'])

    def test_upload_preserves_exact_text_and_blocks_parallel_jobs(self):
        picture = io.BytesIO()
        Image.new('RGB', (100, 100), 'white').save(picture, 'PNG')
        exact_text = 'Hola.\n¡Este texto, exactamente! 123'
        with tempfile.TemporaryDirectory() as directory, patch.object(application, 'DATA', Path(directory)), patch.object(application, 'readiness', return_value=[]), patch.object(application.pool, 'submit') as submit:
            response = self.client.post('/api/jobs', data={'text': exact_text, 'voice': 'es-ES-ElviraNeural', 'image': (io.BytesIO(picture.getvalue()), 'foto.png')})
            self.assertEqual(response.status_code, 202)
            job_id = response.json['id']
            self.assertEqual(submit.call_args.args[2], exact_text)
            self.assertTrue((Path(directory) / job_id / 'portrait.png').exists())
            second = self.client.post('/api/jobs', data={'text': 'Hola', 'voice': 'es-ES-ElviraNeural', 'image': (io.BytesIO(picture.getvalue()), 'foto.png')})
            self.assertEqual(second.status_code, 409)
            application.update(job_id, status='done')
            (Path(directory) / job_id / 'video.mp4').write_bytes(b'test-video')
            video = self.client.get(f'/api/jobs/{job_id}/video?download=1')
            self.assertEqual(video.status_code, 200)
            self.assertIn('attachment', video.headers['Content-Disposition'])
            video.close()

    def test_invalid_image_releases_queue(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(application, 'DATA', Path(directory)), patch.object(application, 'readiness', return_value=[]):
            result = self.client.post('/api/jobs', data={'text': 'Hola', 'voice': 'es-ES-ElviraNeural', 'image': (io.BytesIO(b'invalid'), 'foto.png')})
            self.assertEqual(result.status_code, 400)
            self.assertTrue(all(job['status'] == 'error' for job in application.jobs.values()))


if __name__ == '__main__':
    unittest.main()
