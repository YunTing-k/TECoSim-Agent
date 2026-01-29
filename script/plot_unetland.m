%+FHDR//////////////////////////////////////////////////////////////////////////////
% Company: Shanghai Jiao Tong University
% Engineer: Yu Huang
% Coding: UTF-8
% Create Date: 2026.1.29
% Description:
% Plot the UnetLand train loss, test results
%
% Revision:
% ---------------------------------------------------------------------------------
% [Date]         [By]         [Version]         [Change Log]
% ---------------------------------------------------------------------------------
% 2026/1/29      Yu Huang     1.0               First implementation
% ---------------------------------------------------------------------------------
%
%-FHDR//////////////////////////////////////////////////////////////////////////////
clc
clear
close all
%% Params
data_path = 'G:\case-19\model\unetland4';
model = 'unetland';
test_path = 'test1';
test_case = 'unetland_test19_OOD4';
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
%% Plot test error 2D
test_data = load([data_path, '\', test_path, '\',test_case]);
v_real_relative = test_data.v_real_relative;
v_predict_relative = test_data.v_predict_relative;
v_err = test_data.v_err;

cmap = slanCM("spectral");
cmap = flipud(cmap);

fig0 = figure;
imagesc(v_real_relative)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','a.u.');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
daspect([1 1 1])
set(fig0,'PaperPositionMode','manual');
set(fig0,'PaperUnits','points');
print(fig0,[test_case, '_v_real2D.jpg'],'-r600','-djpeg');

fig0 = figure;
imagesc(v_predict_relative)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','a.u.');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
daspect([1 1 1])
set(fig0,'PaperPositionMode','manual');
set(fig0,'PaperUnits','points');
print(fig0,[test_case, '_v_predict2D.jpg'],'-r600','-djpeg');
%% Plot test error 3D
cmap = slanCM("spectral");
cmap = flipud(cmap);

fig2 = figure;
mesh(v_real_relative)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','a.u.');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
set(fig2,'PaperPositionMode','manual');
set(fig2,'PaperUnits','points');
print(fig2,[test_case, '_v_real3D.jpg'],'-r600','-djpeg');

fig3 = figure;
mesh(v_predict_relative)
box on
c_bar = colorbar;
xlabel('Col')
ylabel('Row')
set(get(c_bar,'title'),'string','a.u.');
colormap(cmap)
set(gca,'FontName','Times New Roman','FontWeight','normal')
set(fig3,'PaperPositionMode','manual');
set(fig3,'PaperUnits','points');
print(fig3,[test_case, '_v_predict3D.jpg'],'-r600','-djpeg');
