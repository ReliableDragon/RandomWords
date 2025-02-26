
from tempfile import TemporaryDirectory, NamedTemporaryFile

class TestDirectories():

  def get_rooted(self, path):
    return '/' + self.root + path.removeprefix(self.root)

  def write_file(self, file, txt):
    with open(file.name, 'w') as f:
      f.write(txt)

  def __enter__(self):
    self.d1 = TemporaryDirectory()
    self.d2 = TemporaryDirectory(dir=self.d1.name)
    self.d3 = TemporaryDirectory(dir=self.d2.name, prefix='z')
    self.d4 = TemporaryDirectory(dir=self.d2.name, prefix='a')

    self.tf1 = NamedTemporaryFile(suffix='.txt', prefix='tf1', dir=self.d1.name)
    self.tf2 = NamedTemporaryFile(suffix='.txt', prefix='tf2', dir=self.d2.name)
    self.tf3 = NamedTemporaryFile(suffix='.txt', prefix='a', dir=self.d3.name)
    self.tf4 = NamedTemporaryFile(suffix='.txt', prefix='z', dir=self.d3.name)
    self.tf5 = NamedTemporaryFile(suffix='.txt', prefix='tf5', dir=self.d4.name)

    self.write_file(self.tf1, 'a\nb\nc\n')
    self.write_file(self.tf2, 'scout\nheavy\nmedic')
    self.write_file(self.tf3, 'robophicles aeschylinux euripiDOS')
    self.write_file(self.tf4, '1\n2\n3\n4\n5\n6\n7')
    self.write_file(self.tf5, 'five')

    self.ntf1 = NamedTemporaryFile(suffix='.mp3', dir=self.d1.name)
    self.ntf2 = NamedTemporaryFile(suffix='.mp4', dir=self.d2.name)
    self.ntf3 = NamedTemporaryFile(suffix='.mp5', dir=self.d2.name)

    self.txts = [self.tf1.name, self.tf2.name, self.tf3.name, self.tf4.name, self.tf5.name]
    self.root = self.d1.name + '/'

    self.d1_name = self.d1.name.strip('/').split('/')[-1] + '/'
    self.d2_name = self.d2.name.removeprefix(self.root).lstrip('/') + '/'
    self.d3_name = self.d3.name.removeprefix(self.d2.name).lstrip('/') + '/'
    self.d4_name = self.d4.name.removeprefix(self.d2.name).lstrip('/') + '/'

    self.tf1_name = self.tf1.name.removeprefix(self.root).lstrip('/')
    self.tf2_name = self.tf2.name.removeprefix(self.d2.name).lstrip('/')
    self.tf3_name = self.tf3.name.removeprefix(self.d3.name).lstrip('/')
    self.tf4_name = self.tf4.name.removeprefix(self.d3.name).lstrip('/')
    self.tf5_name = self.tf5.name.removeprefix(self.d4.name).lstrip('/')


    self.ntf1_name = self.ntf1.name.removeprefix(self.root).lstrip('/')
    self.ntf2_name = self.ntf2.name.removeprefix(self.d2.name).lstrip('/')
    self.ntf3_name = self.ntf3.name.removeprefix(self.d4.name).lstrip('/')

    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.tf1.close()
    self.tf2.close()
    self.tf3.close()
    self.tf4.close()
    self.tf5.close()

    self.ntf1.close()
    self.ntf2.close()
    self.ntf3.close()

    self.d1.cleanup()
    self.d2.cleanup()
    self.d3.cleanup()
    self.d4.cleanup()

    return False
