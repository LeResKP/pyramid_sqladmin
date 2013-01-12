<%inherit file="base.mak" />

<ul>
% for name, link in links:
  <li><a href="${link}">${name}</a></li>
% endfor
</ul>
