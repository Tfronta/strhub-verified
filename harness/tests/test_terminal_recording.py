import pathlib
import subprocess


HARNESS = pathlib.Path(__file__).resolve().parents[1]


def test_transcript_contains_the_launch_and_unmodified_output(tmp_path):
    output_log = tmp_path / "log.txt"
    program = tmp_path / "probe.sh"
    program.write_text('printf "received: <%s>\\n" "$1"\nprintf "error: line 2\\n" >&2\nexit 17\n')

    result = subprocess.run(
        ["bash", str(HARNESS / "record_terminal.sh"), str(output_log),
         "bash", "probe.sh", "reads one.bam"],
        cwd=tmp_path, capture_output=True,
    )

    expected_output = b"received: <reads one.bam>\nerror: line 2\n"
    assert result.returncode == 17
    assert result.stdout == output_log.read_bytes() == expected_output
    assert (tmp_path / "log.txt.terminal").read_bytes() == (
        b"$ bash probe.sh reads\\ one.bam\n" + expected_output + b"\n[exit 17]\n"
    )
