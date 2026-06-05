import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator, Optional, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    RunnableConfig,
    get_checkpoint_id,
    get_checkpoint_metadata,
    WRITES_IDX_MAP,
)

logger = logging.getLogger(__name__)

class AsyncMongoDBSaver(BaseCheckpointSaver):
    def __init__(self, db, *, serde=None):
        super().__init__(serde=serde)
        self.db = db

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    @classmethod
    def from_conn_string(cls, conn_string: str, db_name: str = "checkpointing_db", **kwargs):
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(conn_string)
        db = client[db_name]
        return cls(db, **kwargs)

    # Sync methods are disabled in fully async environment
    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        raise NotImplementedError("Use aget_tuple instead")

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        raise NotImplementedError("Use alist instead")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use aput instead")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        raise NotImplementedError("Use aput_writes instead")

    def delete_thread(self, thread_id: str) -> None:
        raise NotImplementedError("Use adelete_thread instead")

    # Async methods
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        if checkpoint_id:
            # Read from history
            doc = await self.db.checkpoints.find_one({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            })
        else:
            # Read from conversations cache
            doc = await self.db.conversations.find_one({
                "thread_id": thread_id,
            })

        if not doc or "checkpoint" not in doc:
            return None

        resolved_checkpoint_id = doc.get("checkpoint_id") or doc.get("latest_checkpoint_id") or checkpoint_id
        if not resolved_checkpoint_id:
            return None

        # Load checkpoint dict
        c_doc = doc["checkpoint"]
        checkpoint_dict = self.serde.loads_typed((c_doc["type"], c_doc["bytes"]))

        # Load blobs
        channel_values = {}
        for k, ver in checkpoint_dict.get("channel_versions", {}).items():
            blob_doc = await self.db.checkpoint_blobs.find_one({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "channel": k,
                "version": ver,
            })
            if blob_doc and blob_doc.get("type") != "empty":
                channel_values[k] = self.serde.loads_typed((blob_doc["type"], blob_doc["bytes"]))

        checkpoint_dict["channel_values"] = channel_values

        # Load writes
        writes_cursor = self.db.checkpoint_writes.find({
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": resolved_checkpoint_id,
        })
        writes_docs = await writes_cursor.to_list(length=None)
        pending_writes = []
        for w in writes_docs:
            val = self.serde.loads_typed((w["type"], w["bytes"]))
            pending_writes.append((w["task_id"], w["channel"], val))

        m_doc = doc["metadata"]
        metadata = self.serde.loads_typed((m_doc["type"], m_doc["bytes"]))
        parent_checkpoint_id = doc.get("parent_checkpoint_id")

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": resolved_checkpoint_id,
                }
            },
            checkpoint=checkpoint_dict,
            metadata=metadata,
            pending_writes=pending_writes,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            ),
        )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        query = {}
        if config:
            query["thread_id"] = config["configurable"]["thread_id"]
            if "checkpoint_ns" in config["configurable"]:
                query["checkpoint_ns"] = config["configurable"]["checkpoint_ns"]
            checkpoint_id = get_checkpoint_id(config)
            if checkpoint_id:
                query["checkpoint_id"] = checkpoint_id

        if before:
            before_checkpoint_id = get_checkpoint_id(before)
            if before_checkpoint_id:
                query["checkpoint_id"] = {"$lt": before_checkpoint_id}

        cursor = self.db.checkpoints.find(query, sort=[("checkpoint_id", -1)])
        
        counter = 0
        async for doc in cursor:
            if limit is not None and counter >= limit:
                break

            m_doc = doc["metadata"]
            metadata = self.serde.loads_typed((m_doc["type"], m_doc["bytes"]))
            if filter and not all(metadata.get(k) == v for k, v in filter.items()):
                continue

            thread_id = doc["thread_id"]
            checkpoint_ns = doc["checkpoint_ns"]
            checkpoint_id = doc["checkpoint_id"]

            # Load checkpoint dict
            c_doc = doc["checkpoint"]
            checkpoint_dict = self.serde.loads_typed((c_doc["type"], c_doc["bytes"]))

            # Load blobs
            channel_values = {}
            for k, ver in checkpoint_dict.get("channel_versions", {}).items():
                blob_doc = await self.db.checkpoint_blobs.find_one({
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": k,
                    "version": ver,
                })
                if blob_doc and blob_doc.get("type") != "empty":
                    channel_values[k] = self.serde.loads_typed((blob_doc["type"], blob_doc["bytes"]))

            checkpoint_dict["channel_values"] = channel_values

            # Load writes
            writes_cursor = self.db.checkpoint_writes.find({
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            })
            writes_docs = await writes_cursor.to_list(length=None)
            pending_writes = []
            for w in writes_docs:
                val = self.serde.loads_typed((w["type"], w["bytes"]))
                pending_writes.append((w["task_id"], w["channel"], val))

            parent_checkpoint_id = doc.get("parent_checkpoint_id")
            counter += 1

            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                },
                checkpoint=checkpoint_dict,
                metadata=metadata,
                pending_writes=pending_writes,
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": parent_checkpoint_id,
                        }
                    }
                    if parent_checkpoint_id
                    else None
                ),
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]

        c = checkpoint.copy()
        values = c.pop("channel_values", {})

        # Extract metadata for indexed fields
        organization_id = values.get("organization_id")
        platform = values.get("platform")
        sender_id = values.get("sender_id")
        chat_id = values.get("chat_id")
        bot_name = values.get("bot_name")
        customer_name = values.get("customer_name")
        ai_assigned = values.get("ai_assigned", False)
        assigned_user = values.get("assigned_user")
        previous_summary = values.get("previous_summary")
        summarized_count = values.get("summarized_count", 0)

        # Save blobs for new versions
        for k, v in new_versions.items():
            blob_type, blob_bytes = self.serde.dumps_typed(values[k]) if k in values else ("empty", b"")
            await self.db.checkpoint_blobs.update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": k,
                    "version": v,
                },
                {
                    "$set": {
                        "type": blob_type,
                        "bytes": blob_bytes,
                    }
                },
                upsert=True
            )

        c_type, c_bytes = self.serde.dumps_typed(c)
        meta_type, meta_bytes = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        # Save checkpoints history doc
        await self.db.checkpoints.update_one(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
            {
                "$set": {
                    "checkpoint": {"type": c_type, "bytes": c_bytes},
                    "metadata": {"type": meta_type, "bytes": meta_bytes},
                    "parent_checkpoint_id": parent_checkpoint_id,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        # Build user data
        user_data = {
            "sender_id": sender_id,
            "sender_name": customer_name or "Unknown",
            "sender_username": None,
            "profile_pic": None
        }

        # Keep existing username/profile_pic if present
        existing = await self.db.conversations.find_one({"thread_id": thread_id})
        if existing and "user" in existing:
            for key in ["sender_username", "profile_pic"]:
                if existing["user"].get(key) and not user_data.get(key):
                    user_data[key] = existing["user"][key]
            if existing["user"].get("sender_name") and existing["user"]["sender_name"] != "Unknown":
                user_data["sender_name"] = existing["user"]["sender_name"]

        # Save conversations cache doc (acting as unique thread state and metadata representation)
        await self.db.conversations.update_one(
            {
                "thread_id": thread_id,
            },
            {
                "$set": {
                    "latest_checkpoint_id": checkpoint_id,
                    "checkpoint": {"type": c_type, "bytes": c_bytes},
                    "metadata": {"type": meta_type, "bytes": meta_bytes},
                    "parent_checkpoint_id": parent_checkpoint_id,
                    "organization_id": organization_id,
                    "platform": platform,
                    "sender_id": sender_id,
                    "chat_id": chat_id,
                    "bot_name": bot_name,
                    "user": user_data,
                    "ai_assigned": ai_assigned,
                    "assigned_user": assigned_user,
                    "previous_summary": previous_summary,
                    "summarized_count": summarized_count,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            w_type, w_bytes = self.serde.dumps_typed(value)
            await self.db.checkpoint_writes.update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                    "task_id": task_id,
                    "idx": write_idx,
                },
                {
                    "$set": {
                        "channel": channel,
                        "type": w_type,
                        "bytes": w_bytes,
                        "task_path": task_path,
                    }
                },
                upsert=True
            )

    async def adelete_thread(self, thread_id: str) -> None:
        await self.db.checkpoints.delete_many({"thread_id": thread_id})
        await self.db.checkpoint_blobs.delete_many({"thread_id": thread_id})
        await self.db.checkpoint_writes.delete_many({"thread_id": thread_id})
        await self.db.conversations.delete_one({"thread_id": thread_id})
