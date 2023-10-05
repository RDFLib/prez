import io
import csv


def render_csv_dropdown(rows: list[dict]) -> io.StringIO:
    stream = io.StringIO()
    headers = list(rows[0].keys())
    writer = csv.DictWriter(
        stream, fieldnames=headers, quotechar='"', quoting=csv.QUOTE_MINIMAL
    )
    writer.writeheader()

    for row in rows:
        writer.writerow(row)

    stream.seek(0)
    return stream
