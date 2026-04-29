%+FHDR//////////////////////////////////////////////////////////////////////////////
% Company: Shanghai Jiao Tong University
% Engineer: Yu Huang
% Coding: UTF-8
% Create Date: 2026.1.23
% Description:
% Plot the PDN injection, distance map, voltage
%
% Revision:
% ---------------------------------------------------------------------------------
% [Date]         [By]         [Version]         [Change Log]
% ---------------------------------------------------------------------------------
% 2026/1/23      Yu Huang     1.0               First implementation
% ---------------------------------------------------------------------------------
%
%-FHDR//////////////////////////////////////////////////////////////////////////////
clc
clear
close all
%% Params
width = 1920;
height = 1080;
data_path = 'G:\case-19\raw_data\pdn120';
frame_idx = 8;
addpath 'C:\Users\12416\Desktop\MatLabFile\库\Tools\slanCM\'
addpath 'C:\Users\12416\Desktop\MatLabFile\库\Tools\altmany-export_fig'
%% Read PDN injection config & save data
content = fileread([data_path, '\config\pdn_injection.json']);
js = jsondecode(content);
bin_map = zeros(height, width);
for i=1:js.amount
    bin_map(js.row(i) + 1, js.col(i) + 1) = 1;
end
cmap = slanCM("viridis");
cmap = flipud(cmap);
fig0 = figure;
imagesc(bin_map)
daspect([1 1 1])
colormap(cmap)
set(gca, 'Color', 'none');
axis off
colorbar off
export_fig('BinMap.png', '-transparent','-r500');

dmap = bwdist(bin_map);
cmap = slanCM("viridis");
cmap = flipud(cmap);
fig1 = figure;
imagesc(dmap)
daspect([1 1 1])
colormap(cmap)
set(gca, 'Color', 'none');
axis off
colorbar off
export_fig('DistanceMap.png', '-transparent','-r500');
%% Read voltage & save data
cmap = slanCM("spectral");
cmap = flipud(cmap);
fid = fopen([data_path, '\voltage\V_', num2str(frame_idx), '.bin'], "r");
vdata = fread(fid, [1920, 1080], "double")';
fclose(fid);

fig2 = figure;
imagesc(vdata)
daspect([1 1 1])
colormap(cmap)
set(gca, 'Color', 'none');
axis off
colorbar off
export_fig('IRDrop.png', '-transparent','-r500');
