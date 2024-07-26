import { Controller, Post, Delete, Param, Get, Put, Body, NotFoundException, Logger } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiParam } from '@nestjs/swagger';
import { DirigeraService } from './dirigera.service';
import { Vec3 } from '@/common/interfaces/color.interface';

@ApiTags('Consumer: Dirigera')
@Controller('consumers/dirigera')
export class DirigeraController {
  private readonly logger = new Logger(DirigeraController.name);

  constructor(private readonly dirigeraService: DirigeraService) {}

  @Get('lights')
  @ApiOperation({ summary: 'Get all lights' })
  async getLights() {
    try {
      return await this.dirigeraService.getLights();
    } catch (error) {
      this.logger.error('Error getting lights:', error);
      throw new NotFoundException('Lights not found');
    }
  }

  @Get('lights/:lightId')
  @ApiOperation({ summary: 'Get a light by ID' })
  @ApiParam({ name: 'lightId', description: 'Light ID' })
  async getLightById(@Param('lightId') lightId: string) {
    try {
      return await this.dirigeraService.getLightById(lightId);
    } catch (error) {
      this.logger.error(`Error getting light by ID ${lightId}:`, error);
      throw new NotFoundException(`Light with ID ${lightId} not found`);
    }
  }

  @Post('lights/:providerId/:lightId')
  @ApiOperation({ summary: 'Add a light to a provider' })
  @ApiParam({ name: 'providerId', description: 'Provider ID' })
  @ApiParam({ name: 'lightId', description: 'Light ID' })
  async addLightToAccount(@Param('providerId') providerId: string, @Param('lightId') lightId: string) {
    try {
      return await this.dirigeraService.addLightToProvider(providerId, lightId);
    } catch (error) {
      this.logger.error(`Error adding light to provider:`, error);
      throw new NotFoundException('Unable to add light to provider');
    }
  }

  @Delete('lights/:lightId')
  @ApiOperation({ summary: 'Remove a light from an account' })
  @ApiParam({ name: 'lightId', description: 'Light ID' })
  async removeLightFromAccount(@Param('lightId') lightId: string) {
    try {
      return await this.dirigeraService.removeLightFromAccount(lightId);
    } catch (error) {
      this.logger.error(`Error removing light from account:`, error);
      throw new NotFoundException('Unable to remove light from account');
    }
  }

  @Put('lights/:lightId/hsl')
  @ApiOperation({ summary: 'Set the HSL color of a light' })
  @ApiParam({ name: 'lightId', description: 'Light ID' })
  async setLightHSL(@Param('lightId') lightId: string, @Body() hsl: Vec3) {
    try {
      return await this.dirigeraService.setLightHSL(lightId, hsl);
    } catch (error) {
      this.logger.error(`Error setting HSL for light ${lightId}:`, error);
      throw new NotFoundException(`Unable to set HSL for light ${lightId}`);
    }
  }
}
