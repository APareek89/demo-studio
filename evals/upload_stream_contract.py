"""Bounded-memory source uploads and failure cleanup; no network/providers."""
from __future__ import annotations
import asyncio
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

_root = Path(tempfile.mkdtemp(prefix="demo-upload-contract-"))
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=str(_root / "demos"),
                  DEMO_STUDIO_GRAPH_DB=str(_root / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException, UploadFile
from server import config, store
from server.app import add_sources, align_message

passed = []
def check(name, truth):
    assert truth, name
    passed.append(name)
    print("PASS", name)

def blocked(*args, **kwargs):
    raise AssertionError("Outbound socket forbidden")

class Bounded(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.largest = 0
    def read(self, size=-1):
        assert 0 < size <= 1024 * 1024, "unbounded upload read"
        self.largest = max(self.largest, size)
        return super().read(size)

async def main():
    demo = store.new_demo("Upload fixture")
    did = demo["id"]
    payload = b"local video bytes" * 200000
    stream = Bounded(payload)
    result = await add_sources(did, [UploadFile(stream, filename="film.mp4", size=len(payload))], "product", "", "", "brand")
    src = result["added"][0]
    check("upload bounded at one MiB per read", stream.largest == 1024 * 1024)
    check("complete original bytes preserved", store.path(did, src["path"]).read_bytes() == payload)
    check("metadata preserves filename kind size role", (src["name"],src["kind"],src["size"],src["role"]) == ("film.mp4","video",len(payload),"product"))
    check("no uploading residue on success", not list(store.path(did,"sources").glob("*.uploading")))
    before = store.load(did)["sources"]
    files_before = set(store.path(did,"sources").iterdir())
    with patch.object(config,"MAX_UPLOAD_MB",1):
        for title, size, content, expected in [
            ("known oversized upload",2*1024*1024,b"",413),
            ("unknown-size oversized upload",None,b"x"*(1024*1024+1),413),
            ("empty upload",0,b"",400),
            ("unsupported upload",3,b"abc",400),
        ]:
            filename="bad.exe" if title=="unsupported upload" else "bad.mp4"
            stream=Bounded(content)
            try:
                await add_sources(did,[UploadFile(stream,filename=filename,size=size)],"product","","","brand")
                raise AssertionError("expected rejection")
            except HTTPException as e:
                check(title+" returns correct status",e.status_code==expected)
            check(title+" leaves no source or file",store.load(did)["sources"]==before and set(store.path(did,"sources").iterdir())==files_before)
        exact=store.add_stream_source(did,"exact.md",Bounded(b"x"*(1024*1024)),max_bytes=1024*1024)
        check("exact size limit accepted",exact["size"]==1024*1024)
    class Failed(Bounded):
        def read(self,size=-1):
            if self.tell(): raise OSError("simulated source interruption")
            return super().read(size)
    before_files=set(store.path(did,"sources").iterdir())
    try: store.add_stream_source(did,"broken.mp4",Failed(b"x"*(1024*1024+1)))
    except OSError: pass
    else: raise AssertionError("stream failure should propagate")
    check("interrupted copy cleans partial bytes",set(store.path(did,"sources").iterdir())==before_files)
    with patch.object(store,"update",side_effect=OSError("simulated metadata failure")):
        try: store.add_stream_source(did,"unregistered.mp4",Bounded(b"abc"))
        except OSError: pass
        else: raise AssertionError("metadata failure should propagate")
    check("metadata failure cleans unregistered file",set(store.path(did,"sources").iterdir())==before_files)
    legacy=store.add_file_source(did,"legacy.md",b"Existing bytes caller")
    check("existing byte-source callers stay compatible",store.path(did,legacy["path"]).read_bytes()==b"Existing bytes caller")
    with patch("server.app.graph.handle_message", return_value={"ok":True}) as handle:
        await align_message(did,"new source",[UploadFile(Bounded(payload),filename="align.mp4",size=len(payload))],"align")
        attached=handle.call_args.args[2][0]
        check("Align attachments use the same bounded stream",store.path(did,attached["path"]).read_bytes()==payload)
        with patch.object(config,"MAX_UPLOAD_MB",1):
            try: await align_message(did,"too large",[UploadFile(Bounded(payload),filename="align.mp4",size=None)],"align")
            except HTTPException as e: check("Align applies source limit before invoking the agent",e.status_code==413 and handle.call_count==1)
            else: raise AssertionError("Align must reject oversized sources")
    collision=store.path(did,"sources/src_abcdef_collision.md.uploading")
    collision.write_bytes(b"owned by another upload")
    with patch.object(store.secrets,"token_hex",return_value="abcdef"):
        try: store.add_stream_source(did,"collision.md",Bounded(b"replacement"))
        except FileExistsError: pass
        else: raise AssertionError("temporary upload collision must not overwrite")
    check("temporary-file collision preserves the other upload",collision.read_bytes()==b"owned by another upload")

if __name__=="__main__":
    with patch.object(socket.socket,"connect",blocked),patch.object(socket,"create_connection",blocked):
        asyncio.run(main())
    print(f"upload stream contract: {len(passed)}/{len(passed)} groups passed")
