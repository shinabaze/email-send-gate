-- may_send(): ask before every email. record_send(): call after every email that went out.
--
-- Marketing is anything a person could reasonably not want: newsletters, follow-ups, offers.
-- Transactional is what they asked for: a receipt, a password reset, a reply to their request.

create or replace function may_send(
  p_email          text,
  p_sender         text,
  p_kind           text,
  p_cooldown_hours int default 24,
  p_daily_cap      int default 100
) returns jsonb
language plpgsql stable as $$
declare
  v_email     text := lower(btrim(p_email));
  v_marketing boolean := p_kind = 'marketing';
  v_contact   contacts%rowtype;
  v_last      timestamptz;
  v_today     int;
  v_known     boolean;
begin
  if p_kind not in ('marketing', 'transactional') then
    raise exception 'p_kind must be marketing or transactional, got %', p_kind;
  end if;
  if v_email is null or v_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    return jsonb_build_object('allow', false, 'reason', 'invalid_email');
  end if;

  -- Leaving a newsletter is not refusing a receipt, so an opt-out only stops marketing.
  if v_marketing and exists (select 1 from opt_outs where email = v_email) then
    return jsonb_build_object('allow', false, 'reason', 'opted_out');
  end if;

  -- A hard bounce stops everything: mailing a dead address again hurts every email you send.
  select * into v_contact from contacts where email = v_email;
  v_known := found;
  if v_known and v_contact.suppressed then
    return jsonb_build_object('allow', false, 'reason', 'suppressed', 'detail', v_contact.suppressed_reason);
  end if;

  if v_marketing then
    -- Someone paying you should hear from you as a customer, not get the sales sequence.
    if exists (select 1 from customers where email = v_email and plan_status = 'active'
               and (paid_until is null or paid_until > now())) then
      return jsonb_build_object('allow', false, 'reason', 'paying_customer');
    end if;
    -- One sender at a time per person, so two campaigns never land in the same inbox.
    if v_known and v_contact.owner not in ('none', p_sender) then
      return jsonb_build_object('allow', false, 'reason', 'owned_by_other_sender', 'detail', v_contact.owner);
    end if;
    select max(sent_at) into v_last from sends where email = v_email and kind = 'marketing';
    if v_last > now() - make_interval(hours => p_cooldown_hours) then
      return jsonb_build_object('allow', false, 'reason', 'cooldown', 'detail', v_last);
    end if;
  end if;

  -- The cap is per sender and counts both kinds: it protects your sending reputation.
  select count(*) into v_today from sends where sender = p_sender and sent_at >= date_trunc('day', now());
  if v_today >= p_daily_cap then
    return jsonb_build_object('allow', false, 'reason', 'daily_cap', 'detail', v_today || '/' || p_daily_cap);
  end if;

  return jsonb_build_object('allow', true, 'reason', 'ok', 'sent_today', v_today);
end $$;


create or replace function record_send(p_email text, p_sender text, p_kind text) returns void
language plpgsql as $$
declare
  v_email text := lower(btrim(p_email));
begin
  insert into sends (email, sender, kind) values (v_email, p_sender, p_kind);
  -- A marketing send claims the person for this sender. A receipt claims nobody: otherwise
  -- the first receipt would block every campaign for that customer.
  if p_kind = 'marketing' then
    insert into contacts (email, owner) values (v_email, p_sender)
    on conflict (email) do update set owner = excluded.owner where contacts.owner = 'none';
  end if;
end $$;


-- When someone finishes with a sender (replied, bought, the sequence ended), let the others in.
create or replace function release_contact(p_email text, p_sender text) returns void
language sql as $$
  update contacts set owner = 'none' where email = lower(btrim(p_email)) and owner = p_sender;
$$;
