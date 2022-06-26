"""
support/seano/views/shared/mermaid.py

Infrastructure to compile Mermaid source into other formats
"""
import os
import re
import subprocess
import sys
import tempfile
from ....system_wide_mutex import SystemWideMutex

FILE_ENCODING_KWARGS = {'encoding': 'utf-8'} if sys.hexversion >= 0x3000000 else {}


def compile_mermaid_to_svg(source, themes=None):
    themes = themes or ['neutral']

    # Create in and out files so that we can talk to mmdc:

    # ABK: Hi!  If you're reading this, you tried to use Python 2 to build this.
    with tempfile.TemporaryDirectory(prefix='zarf_mermaid_compiler_') as folder:

        infile = os.path.join(folder, 'src.mmd')
        outfiles = [os.path.join(folder, x + '.svg') for x in themes]

        with open(infile, "w", **FILE_ENCODING_KWARGS) as f:
            f.write(source)

        for outfile, theme in zip(outfiles, themes):
            _compile_mermaid_on_disk(infile=infile, outfile=outfile, theme=theme)

        # Fetch the text outputted by mmdc:

        result = []
        for outfile in outfiles:
            try:
                with open(outfile, "r", **FILE_ENCODING_KWARGS) as f:
                    result.append(f.read())
            # ABK: Why can't pylint find FileNotFoundError?
            except FileNotFoundError: #pylint: disable=E0602
                print('Hint: mmdc did not create the expected output file:', outfile)
                raise

        # In the rendered output, replace <br> with <br />:
        result = [x.replace('<br>', '<br />') for x in result]

        # mmdc appears to not set the width of the SVG to a real value,
        # which causes the frame of the SVG to keep its height as you
        # scale the width down.  Let's fix up the size data so that the
        # SVG scales properly.
        #
        # Example original SVG:
        #
        # <svg
        #   id="mermaid-1619110767863"
        #   width="100%"                        << this is the main problem
        #   xmlns="http://www.w3.org/2000/svg"
        #   xmlns:xlink="http://www.w3.org/1999/xlink"
        #   height="55"                         << also not good
        #   style="max-width: 185.296875px;"    << not helpful
        #   viewBox="0 0 185.296875 55"
        # > ... many many many more bytes

        def patch_size(svg):
            # Delete all width/hight information, except for the SVG viewBox itself:
            svg = re.sub(r'''\s+width="100%"\s+''', ' ', svg, count=1)
            svg = re.sub(r'''\s+height="[0-9\.]+"\s+''', ' ', svg, count=1)
            svg = re.sub(r'''\s+style="max-width:\s*[0-9a-z\.]+;?"\s+''', ' ', svg, count=1)
            return svg

        result = [patch_size(x) for x in result]

        # And we're finally done!
        return result


def _compile_mermaid_on_disk(infile, outfile, theme):
    """
    Invokes mmdc (a Mermaid compiler) on the given input and output files.

    The output format is auto-deduced from the file extension of the output
    file.

    mmdc is automatically downloaded and installed in a private prefix when
    it does not exist; this usually results in a several second delay on the
    first compilation request.
    """

    # ABK: The Icebox (almost) provides a better implementation than this
    #      clever secret NPM cache & automatic lazy download.  The main
    #      problem right now is that the Icebox would try to fetch "mmdc"
    #      before it tries to fetch "node"; because fetching mmdc requires
    #      access to npm, performing the fetches in the wrong order would
    #      fail.  This can be fixed, but I don't have a lot of time right
    #      now.  Although this approach is objectively not good, it's
    #      fairly well isolated, and implementation details are, for the
    #      most part, kept secret from other modules.  (The only exception
    #      is the exception raised below)
    #
    # ABK: The above comment is now out-of-date.  The Icebox can now be
    #      used to download and prepare the Mermaid compiler.  However,
    #      I do find myself enjoying that this code is so lazy -- it
    #      never gets invoked if the project doesn't need it.  Downloading
    #      mmdc at configure time would circumvent this advantage.

    cwd = os.environ.get('ZARF_MERMAID_NPM_CACHE_DIR')
    mmdc_exec = os.path.join('.', 'node_modules', '.bin',
                             'mmdc.cmd' if sys.platform in ['win32'] else 'mmdc')

    if not cwd:
        raise Exception('Unable to locate the NPM cache directory used by the '
                        'Mermaid compiling infrastructure.  Please set the '
                        'ZARF_MERMAID_NPM_CACHE_DIR environment variable to '
                        'a reasonable temp dir and try again.  Hint: wafexec '
                        'sets ZARF_MERMAID_NPM_CACHE_DIR for you; did you mean '
                        'to run this command through wafexec?')

    with SystemWideMutex(os.path.join(cwd, 'lockfile.lck')):
        if not os.path.exists(os.path.join(cwd, mmdc_exec)):
            npm_cmd_name = 'npm.cmd' if sys.platform in ['win32'] else 'npm'
            proc = subprocess.Popen([npm_cmd_name, 'install', '@mermaid-js/mermaid-cli@8.9.2'],
                                    cwd=cwd,
                                    stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            stdout, _ = proc.communicate()
            if proc.returncode:
                raise Exception('Unable to obtain mmdc: ' + stdout)

    cmd = [
        # ABK: Why does this command have to be an absolute path on Windows,
        #      but the NPM command (above) doesn't?
        os.path.join(cwd, mmdc_exec),
        '--input', infile,
        '--output', outfile,
        '--backgroundColor', 'transparent',
        '--theme', theme,
    ]
    subprocess.check_call(cmd, cwd=cwd)
