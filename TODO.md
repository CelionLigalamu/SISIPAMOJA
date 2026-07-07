# TODO

- [x] Replace `profile_edit_view` in `preachingSacco/sisikwaPamoja/views.py` with the tested implementation that edits:
  - [x] MemberProfile fields via `MemberProfileEditForm`
  - [x] Spouse via `SpouseEditForm` (only when `marital_status == 'married'`)
  - [x] Dependants via `modelformset_factory(Dependant)`
- [x] Ensure necessary imports exist in `views.py` (e.g., `get_object_or_404`, `modelformset_factory`, and forms).

- [x] Validate template context keys match `profile_edit.html` (profile_form, spouse_form, dependant_formset, is_married).
- [ ] Run Django system check / quick test command if available.



