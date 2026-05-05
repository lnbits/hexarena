empty_dict: dict[str, str] = {}
empty_list: list[str] = []


async def m001_inital_tables(db):
    """
    Initial unreleased schema for HexArena.
    """

    await db.execute(
        f"""
        CREATE TABLE hexarena.games (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            fee_wallet_id TEXT,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            default_config TEXT NOT NULL DEFAULT '{empty_dict}',
            latest_run_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    await db.execute(
        f"""
        CREATE TABLE hexarena.game_runs (
            id TEXT PRIMARY KEY,
            game_id TEXT NOT NULL,
            status TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{empty_dict}',
            initial_state TEXT NOT NULL DEFAULT '{empty_dict}',
            current_state TEXT NOT NULL DEFAULT '{empty_dict}',
            turn INTEGER NOT NULL DEFAULT 0,
            winner_agent_id TEXT,
            prize_pool_sats INTEGER NOT NULL DEFAULT 0,
            house_fee_sats INTEGER NOT NULL DEFAULT 0,
            tribute_fee_sats INTEGER NOT NULL DEFAULT 0,
            payouts_total_sats INTEGER NOT NULL DEFAULT 0,
            fee_status TEXT NOT NULL DEFAULT 'none',
            fees_settled_at TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    await db.execute(
        f"""
        CREATE TABLE hexarena.agents (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            display_name TEXT,
            status TEXT NOT NULL,
            api_key TEXT,
            payment_hash TEXT,
            payment_request TEXT,
            payout_request TEXT,
            profile TEXT NOT NULL DEFAULT '{empty_dict}',
            inventory TEXT NOT NULL DEFAULT '{empty_list}',
            payout_amount_sats INTEGER NOT NULL DEFAULT 0,
            payout_status TEXT NOT NULL DEFAULT 'none',
            payout_unique_hash TEXT,
            payout_k1 TEXT,
            payout_payment_hash TEXT,
            payout_settled_at TIMESTAMP,
            start_hex_id TEXT,
            is_eliminated BOOLEAN NOT NULL DEFAULT FALSE,
            eliminated_turn INTEGER,
            last_action_turn INTEGER,
            last_seen_at TIMESTAMP,
            joined_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    await db.execute(
        f"""
        CREATE TABLE hexarena.join_requests (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            paid BOOLEAN NOT NULL DEFAULT FALSE,
            claim_token TEXT,
            display_name TEXT,
            profile TEXT NOT NULL DEFAULT '{empty_dict}',
            payment_hash TEXT,
            payment_request TEXT,
            agent_id TEXT,
            expires_at TIMESTAMP,
            settled_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )

    await db.execute(
        f"""
        CREATE TABLE hexarena.actions (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            agent_id TEXT,
            turn INTEGER NOT NULL,
            phase TEXT NOT NULL,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            target_hex TEXT,
            from_hex TEXT,
            to_hex TEXT,
            target_agent_id TEXT,
            powerup_type TEXT,
            amount INTEGER,
            message TEXT,
            thought TEXT NOT NULL DEFAULT '{empty_dict}',
            payload TEXT NOT NULL DEFAULT '{empty_dict}',
            outcome TEXT NOT NULL DEFAULT '{empty_dict}',
            resolution_order INTEGER,
            resolved_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )
