import { Injectable, OnModuleInit, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { createDirigeraClient, DirigeraClient } from 'dirigera';
import { Repository } from 'typeorm';
import { Consumer } from '../consumer.entity';
import { Provider } from '@/providers/provider.entity';
import { ConsumerEnum } from '@/common/enums/consumers.enum';
import { Vec3 } from '@/common/interfaces/color.interface';

@Injectable()
export class DirigeraService implements OnModuleInit {
  private readonly logger = new Logger(DirigeraService.name);
  private client: DirigeraClient;

  constructor(
    @InjectRepository(Consumer)
    private consumerRepository: Repository<Consumer>,
    @InjectRepository(Provider)
    private providerRepository: Repository<Provider>,
  ) {}

  async onModuleInit() {
    try {
      this.client = await createDirigeraClient({
        accessToken: process.env.DIRIGERA_ACCESS_TOKEN,
      });
    } catch (error) {
      this.logger.error('Error initializing Dirigera client:', error);
      throw new Error('Failed to initialize Dirigera client');
    }
  }

  async getLights() {
    try {
      return await this.client.lights.list();
    } catch (error) {
      this.logger.error('Error fetching lights:', error);
      throw new Error('Failed to fetch lights');
    }
  }

  async getEnabledLights() {
    try {
      return await this.consumerRepository.find({
        where: { type: ConsumerEnum.Dirigera },
      });
    } catch (error) {
      this.logger.error('Error fetching enabled lights:', error);
      throw new Error('Failed to fetch enabled lights');
    }
  }

  async getLightById(lightId: string) {
    try {
      return await this.client.lights.get({ id: lightId });
    } catch (error) {
      this.logger.error(`Error fetching light by ID ${lightId}:`, error);
      throw new Error(`Failed to fetch light by ID ${lightId}`);
    }
  }

  async addLightToProvider(providerId: string, lightId: string) {
    const light = await this.getLightById(lightId);
    const provider = await this.providerRepository.findOne({
      where: { id: providerId },
    });

    if (!provider || !light) {
      this.logger.error(`Provider ${providerId} or light ${lightId} not found`);
      return null;
    }

    return this.consumerRepository.save({
      name: light.attributes.customName,
      identifier: light.id,
      type: ConsumerEnum.Dirigera,
      provider,
    });
  }

  async setLightHSL(lightId: string, hsl: Vec3) {
    try {
      await this.client.lights.setIsOn({ id: lightId, isOn: true });

      await this.client.lights.setLightColor({
        id: lightId,
        colorHue: hsl[0] * 360,
        colorSaturation: hsl[1],
        transitionTime: 2000,
      });

      // await this.client.lights.setLightLevel({
      //   id: lightId,
      //   lightLevel: 50,
      //   transitionTime: 2000,
      // });
    } catch (error) {
      this.logger.error(`Error setting light HSL for ${lightId}:`, error);
      throw new Error(`Failed to set light HSL for ${lightId}`);
    }
  }

  async removeLightFromAccount(id: string) {
    try {
      return await this.consumerRepository.delete({ id });
    } catch (error) {
      this.logger.error(`Error removing light from account ${id}:`, error);
      throw new Error(`Failed to remove light from account ${id}`);
    }
  }
}
