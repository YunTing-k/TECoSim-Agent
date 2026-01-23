%+FHDR//////////////////////////////////////////////////////////////////////////////
% Company: Shanghai Jiao Tong University
% Engineer: Yu Huang
% Coding: UTF-8
% Create Date: 2026.1.23
% Description:
% Plot the NN train loss, test results
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
data_path = 'G:\case-19\model\unet1';
model = 'unet';
addpath 'C:\Users\12416\Desktop\MatLabFile\库\Tools\slanCM\'
addpath 'C:\Users\12416\Desktop\MatLabFile\库\Tools\altmany-export_fig'
%% Plot train loss
train_loss = load([data_path, '\', model, '_train_loss.mat']).data;
train_loss = train_loss';
train_loss = train_loss(:);

figure
hold on
box on
grid on
plot(train_loss, 'LineWidth', 1);
xlabel("Iteration (#)")
ylabel("Loss")
set(gca,'FontName','Times New Roman','FontWeight','normal')
set(gca,'YScale','log')
%% Plot test error
test_data = load([data_path, '\', model, '_test.mat']);
v_real = test_data.v_real;
v_predict = test_data.v_predict;
v_err = test_data.v_err;

cmap = slanCM("spectral");
cmap = flipud(cmap);

fig0 = figure;
imagesc(v_real)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','V (V)');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
daspect([1 1 1])
set(fig0,'PaperPositionMode','manual');
set(fig0,'PaperUnits','points');
% set(fig,'PaperPosition',[0,0,1920,1080]);
print(fig0,'v_real.jpg','-r600','-djpeg');

fig0 = figure;
imagesc(v_predict)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','V (V)');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
daspect([1 1 1])
set(fig0,'PaperPositionMode','manual');
set(fig0,'PaperUnits','points');
% set(fig,'PaperPosition',[0,0,1920,1080]);
print(fig0,'v_predict.jpg','-r600','-djpeg');
