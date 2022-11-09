import os
import re
import typing
from datetime import datetime
from pathlib import Path

import click
import internetarchive
import pytz
from retry import retry
from rich import print

from . import utils


@click.command()
@click.argument("handle")
@click.option("-i", "--input-dir", "input_dir", default="./")
@click.option(
    "--bundle",
    "is_bundle",
    is_flag=True,
    default=False,
    help="The provided handle is a bundle",
)
@click.option(
    "--verbose",
    "verbose",
    is_flag=True,
    default=False,
    help="Display the upload progress to archive.org",
)
def cli(handle: str, input_dir: str, is_bundle: bool = False, verbose: bool = False):
    """Save a webpage screenshot to an archive.org collection."""
    input_path = Path(input_dir).absolute()
    assert input_path.exists()

    if is_bundle:
        # Get all the sites
        site_list = utils.get_sites_in_bundle(handle)
        for site in site_list:
            _upload(site, input_path, verbose)

    else:
        # Pull the source’s metadata
        site = utils.get_site(handle)

        # Upload it
        _upload(site, input_path, verbose)


def _clean_handle(s):
    s = s.lower()
    # Replace any leading underscores, which don't work on archive.org
    s = re.sub("^(_+)", "", s)
    return s


@retry(tries=3, delay=5, backoff=2)
def _upload(data: dict, input_dir: Path, verbose: bool = False):
    # Set the input paths
    handle = _clean_handle(data["handle"])
    image_path = input_dir / f"{handle}.jpg"
    a11y_path = input_dir / f"{handle}.accessibility.json"
    hyperlinks_path = input_dir / f"{handle}.hyperlinks.json"
    lighthouse_path = input_dir / f"{handle}.lighthouse.json"
    wayback_path = input_dir / f"{handle}.wayback.json"

    # Get the timestamp
    now = datetime.now()

    # Convert it to local time
    tz = pytz.timezone(data["timezone"])
    now_local = now.astimezone(tz)
    now_iso = now_local.isoformat()

    # We will post into an "item" keyed to the site's handle and year
    identifier = f"{handle}-{now_local.strftime('%Y')}"

    # Grab the files that exist
    file_dict = {}
    if image_path.exists():
        file_dict[f"{handle}-{now_iso}.jpg"] = image_path
    if a11y_path.exists():
        file_dict[f"{handle}-{now_iso}.accessibility.json"] = a11y_path
    if hyperlinks_path.exists():
        file_dict[f"{handle}-{now_iso}.hyperlinks.json"] = hyperlinks_path
    if lighthouse_path.exists():
        file_dict[f"{handle}-{now_iso}.lighthouse.json"] = lighthouse_path
    if wayback_path.exists():
        file_dict[f"{handle}-{now_iso}.wayback.json"] = wayback_path

    # If there are no file, squawk but move on
    if not file_dict:
        print(f"No files found for {data['handle']}")
        return

    # Get secrets
    access_key: typing.Optional[str] = os.getenv("IA_ACCESS_KEY")
    secret_key: typing.Optional[str] = os.getenv("IA_SECRET_KEY")
    collection: typing.Optional[str] = os.getenv("IA_COLLECTION")

    # Make sure secrets are there
    assert access_key
    assert secret_key
    assert collection

    # Set all the arguments
    kwargs = dict(
        # Authentication
        access_key=access_key,
        secret_key=secret_key,
        # Metadata about the item
        metadata=dict(
            title=f"{data['name']} homepages in {now_local.strftime('%Y')}",
            collection=collection,
            mediatype="image",
            publisher=data["url"],
            date=now_local.strftime("%Y"),
            contributor="https://homepages.news",
            retries=2,
            retries_sleep=10,
        ),
        # Metadata about the image file
        files=file_dict,
        # Other options
        verbose=verbose,
    )

    # Upload it
    internetarchive.upload(identifier, **kwargs)


if __name__ == "__main__":
    cli()
