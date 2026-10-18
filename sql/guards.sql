-- Two triggers that stop a form fill from damaging a customer record.
--
-- Lead forms and signup flows often "upsert" the whole row with fixed defaults. Without these,
-- a paying customer who fills in the contact form is written back as a free lead, and a blank
-- field on the form wipes the company name you already had.
--
-- Both CORRECT the write instead of raising an error: the writers are usually automations that
-- treat a failed insert as success, so an error would only lose the form fill quietly.

create or replace function keep_paying_customer() returns trigger
language plpgsql as $$
begin
  if old.plan_status = 'active' and (old.paid_until is null or old.paid_until > now())
     and new.plan_status = 'none'
     and coalesce(current_setting('gate.allow_downgrade', true), '') <> 'on' then
    new.plan_status := old.plan_status;
    new.paid_until := old.paid_until;
  end if;
  return new;
end $$;

drop trigger if exists keep_paying_customer on customers;
create trigger keep_paying_customer before update on customers
  for each row execute function keep_paying_customer();


create or replace function no_blank_overwrite() returns trigger
language plpgsql as $$
begin
  new.name := coalesce(nullif(btrim(new.name), ''), old.name);
  new.company := coalesce(nullif(btrim(new.company), ''), old.company);
  return new;
end $$;

drop trigger if exists no_blank_overwrite on customers;
create trigger no_blank_overwrite before update on customers
  for each row execute function no_blank_overwrite();
